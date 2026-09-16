/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ExecuteRequest = {
    /**
     * Mission prompt
     */
    query: string;
    /**
     * Mission ID
     */
    mission_id?: (string | null);
    /**
     * GeoJSON polygon or bbox
     */
    aoi?: (Record<string, any> | null);
    /**
     * Time window
     */
    temporal_window?: (Record<string, any> | null);
    /**
     * Tool execution budget constraints
     */
    budget?: (Record<string, any> | null);
};

