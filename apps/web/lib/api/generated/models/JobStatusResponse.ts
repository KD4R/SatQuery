/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobStatus } from './JobStatus';
export type JobStatusResponse = {
    job_id: string;
    mission_id: string;
    status: JobStatus;
    submitted_at: string;
    started_at: (string | null);
    completed_at: (string | null);
    error_message: (string | null);
    trace_id: (string | null);
};

