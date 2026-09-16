/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PlanStep } from './PlanStep';
export type PlanResponse = {
    mission_id: string;
    intent: Record<string, any>;
    plan_steps: Array<PlanStep>;
    selected_sensors: Array<string>;
    trace_id?: (string | null);
};

