/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PlanRequest = {
    /**
     * Natural language mission objective
     */
    query: string;
    /**
     * Optional associated mission ID
     */
    mission_id?: (string | null);
    /**
     * Optional GeoJSON AOI geometry
     */
    aoi?: (Record<string, any> | null);
    /**
     * Contextual metadata
     */
    metadata?: Record<string, any>;
};

