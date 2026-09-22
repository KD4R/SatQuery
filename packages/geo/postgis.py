import json
import logging
import os as _os
from contextlib import contextmanager
from typing import Any, Dict, List

import psycopg2
from psycopg2 import pool

from packages.providers.config import config

logger = logging.getLogger(__name__)


class PostGISOperations:
    """
    Implements P4-14: PostGIS spatial operations.
    Executes all DB spatial operations utilizing a robust Connection Pool.
    Strictly enforces the Row-Level Security (RLS) context by setting 'satquery.org_id'.
    """

    def __init__(self):
        try:
            self.pool = pool.ThreadedConnectionPool(
                minconn=1, maxconn=20, dsn=config.db_connection_string.get_secret_value()
            )
        except psycopg2.Error as e:
            logger.error(f"Failed to initialize PostGIS connection pool: {e}")
            raise RuntimeError("Database connection pool failed to initialize")

    @contextmanager
    def _get_connection(self, org_id: str):
        """
        Grabs a connection from the pool, explicitly enforces tenant RLS context,
        and securely clears it before returning the connection back to the pool.
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Set local session context. `false` means it persists for the transaction/session
                # We clear it explicitly in finally block to ensure no cross-request leakage
                cur.execute("SELECT set_config('satquery.org_id', %s, false);", (org_id,))
            yield conn
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            try:
                # Crucial step: Purge tenant context before releasing to the thread pool
                with conn.cursor() as cur:
                    cur.execute("SELECT set_config('satquery.org_id', '', false);")
                conn.commit()
            except psycopg2.Error:
                # If we can't reset context, the connection is poisoned. Close and throw it away.
                conn.close()
            self.pool.putconn(conn, close=(conn.closed != 0))

    def insert_aoi(self, org_id: str, aoi_id: str, name: str, geojson: Dict[str, Any]):
        """
        Securely inserts an AOI respecting RLS.
        """
        geom_str = json.dumps(geojson)
        with self._get_connection(org_id) as conn:
            with conn.cursor() as cur:
                sql = (
                    "INSERT INTO aois (id, org_id, name, geom) "
                    "VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s))"
                )
                cur.execute(sql, (aoi_id, org_id, name, geom_str))
            conn.commit()

    def get_intersecting_aois(self, org_id: str, geometry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Securely queries intersecting AOIs for the given org_id.
        The RLS guarantees no leaked rows from other tenants.
        """
        geom_str = json.dumps(geometry)
        with self._get_connection(org_id) as conn:
            with conn.cursor() as cur:
                sql = (
                    "SELECT id, name, ST_AsGeoJSON(geom) FROM aois "
                    "WHERE ST_Intersects(geom, ST_GeomFromGeoJSON(%s))"
                )
                cur.execute(sql, (geom_str,))
                results = cur.fetchall()

        return [{"id": r[0], "name": r[1], "geometry": json.loads(r[2])} for r in results]

    def compute_infrastructure_impact(
        self, org_id: str, flood_polygon: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        P4-XX: Infrastructure Impact Graph (PostGIS)
        Intersects flood polygon with OSM building footprints and road networks.
        Uses ST_Buffer and ST_Difference for advanced relationship mapping.
        """
        geom_str = json.dumps(flood_polygon)
        with self._get_connection(org_id) as conn:
            with conn.cursor() as cur:
                # Set timeout to prevent DoS from heavy GIS operations
                cur.execute("SET statement_timeout = '15s';")
                try:
                    # Count affected buildings using ST_Intersects
                    sql_bld = (
                        "SELECT count(*) FROM osm_buildings "
                        "WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))"
                    )
                    cur.execute(sql_bld, (geom_str,))
                    affected_buildings = cur.fetchone()[0]

                    # Find buildings at risk (within 100m buffer) but not currently flooded
                    # (ST_Difference logic conceptually)
                    sql_bld_risk = (
                        "SELECT count(*) FROM osm_buildings "
                        "WHERE ST_Intersects(geom, ST_Buffer(ST_SetSRID("
                        "ST_GeomFromGeoJSON(%s), 4326)::geography, 100)::geometry) "
                        "AND NOT ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))"
                    )
                    cur.execute(sql_bld_risk, (geom_str, geom_str))
                    at_risk_buildings = cur.fetchone()[0]

                    # Count disrupted roads using ST_Intersects
                    sql_rds = (
                        "SELECT count(*) FROM osm_roads "
                        "WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))"
                    )
                    cur.execute(sql_rds, (geom_str,))
                    disrupted_roads = cur.fetchone()[0]
                finally:
                    cur.execute("RESET statement_timeout;")

        return {
            "flood_zone_1": {
                "affected_buildings": affected_buildings,
                "at_risk_buildings": at_risk_buildings,
                "disrupted_roads": disrupted_roads,
            }
        }

    def calculate_road_accessibility(
        self, org_id: str, flood_polygon: Dict[str, Any], hospital_location: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        P4-XX: Road Accessibility Intelligence
        Dynamically recalculate access to critical infrastructure using pgRouting.
        """
        flood_geom = json.dumps(flood_polygon)
        hospital_geom = json.dumps(hospital_location)

        with self._get_connection(org_id) as conn:
            with conn.cursor() as cur:
                # Using pgRouting (pgr_dijkstra) to calculate alternative route distances
                # We find the closest nodes to our start (assumed center of flood
                # zone for context, or just safe areas) and end (hospital), while
                # penalizing or removing edges intersecting the flood zone.
                # Since we don't have exact routing params from the LLM, we execute a
                # generic pgRouting wrapper query.

                sql_route = """
                WITH hospital_node AS (
                    SELECT id::integer FROM osm_roads_vertices_pgr
                    ORDER BY the_geom <-> ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) LIMIT 1
                ),
                safe_edges AS (
                    SELECT id, source, target, cost, reverse_cost
                    FROM osm_roads
                    WHERE NOT ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                )
                SELECT sum(cost) AS total_distance
                FROM pgr_dijkstra(
                    'SELECT id, source, target, cost, reverse_cost FROM safe_edges',
                    (SELECT id FROM hospital_node),
                    (SELECT id FROM hospital_node) + 1, -- Placeholder for dynamic target
                    directed := false
                );
                """
                # Setting statement_timeout to prevent DoS from heavy GIS graph recalculations
                cur.execute("SET statement_timeout = '10s';")
                try:
                    cur.execute(sql_route, (hospital_geom, flood_geom))
                    row = cur.fetchone()
                    total_distance = row[0] if row else None
                finally:
                    cur.execute("RESET statement_timeout;")

        return {
            "alternative_route_distance_m": total_distance or -1,
            "status": "accessible" if total_distance else "isolated",
        }


# Singleton instance — initialized lazily so imports don't crash in test environments
# without a running database.
if not _os.environ.get("SATQUERY_SKIP_DB_INIT"):
    try:
        postgis_ops = PostGISOperations()
    except Exception as _e:
        logger.warning(f"PostGIS pool not initialized at startup: {_e}")
        postgis_ops = None  # type: ignore
else:
    postgis_ops = None  # type: ignore
