import logging
from typing import List, Dict, Any
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
import json

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
                minconn=1,
                maxconn=20,
                dsn=config.db_connection_string.get_secret_value()
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
                cur.execute(
                    "INSERT INTO aois (id, org_id, name, geom) VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s))",
                    (aoi_id, org_id, name, geom_str)
                )
            conn.commit()

    def get_intersecting_aois(self, org_id: str, geometry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Securely queries intersecting AOIs for the given org_id.
        The RLS guarantees no leaked rows from other tenants.
        """
        geom_str = json.dumps(geometry)
        with self._get_connection(org_id) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, ST_AsGeoJSON(geom) FROM aois WHERE ST_Intersects(geom, ST_GeomFromGeoJSON(%s))",
                    (geom_str,)
                )
                results = cur.fetchall()
                
        return [{"id": r[0], "name": r[1], "geometry": json.loads(r[2])} for r in results]

# Singleton instance — initialized lazily so imports don't crash in test environments
# without a running database. Call postgis_ops() to get the connection pool instance.
import os as _os
if not _os.environ.get("SATQUERY_SKIP_DB_INIT"):
    try:
        postgis_ops = PostGISOperations()
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"PostGIS pool not initialized at startup: {_e}")
        postgis_ops = None
else:
    postgis_ops = None
