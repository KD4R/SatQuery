/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobStatus } from './JobStatus';
export type JobSubmitResponse = {
    job_id: string;
    mission_id: string;
    status: JobStatus;
    submitted_at: string;
    trace_id: (string | null);
    message?: string;
};

