/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ConfidenceResponse = {
    confidence_score: number;
    passed_gate: boolean;
    uncertainty_factors?: Array<string>;
    action: string;
    trace_id?: (string | null);
};

