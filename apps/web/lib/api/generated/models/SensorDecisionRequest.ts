/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SensorDecisionRequest = {
    /**
     * Hazard type: flood, fire, cyclone, landslide
     */
    hazard_type?: string;
    /**
     * Cloud cover percentage
     */
    cloud_cover_percentage?: number;
    /**
     * Whether observation is at night
     */
    is_night?: boolean;
    /**
     * Optimization priority: accuracy, latency, balanced
     */
    priority?: string;
};

