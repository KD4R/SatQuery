/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MissionStatus } from './MissionStatus';
export type MissionResponse = {
    id: string;
    name: string;
    description: (string | null);
    status: MissionStatus;
    aoi_ids: Array<string>;
    organisation_id: string;
    created_by: string;
    created_at: string;
    updated_at: string;
};

