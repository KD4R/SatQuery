/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ConfidenceRequest } from '../models/ConfidenceRequest';
import type { ConfidenceResponse } from '../models/ConfidenceResponse';
import type { ExecuteRequest } from '../models/ExecuteRequest';
import type { ExecuteResponse } from '../models/ExecuteResponse';
import type { JobStatusResponse } from '../models/JobStatusResponse';
import type { JobSubmitResponse } from '../models/JobSubmitResponse';
import type { MissionCreate } from '../models/MissionCreate';
import type { MissionListResponse } from '../models/MissionListResponse';
import type { MissionResponse } from '../models/MissionResponse';
import type { MissionState } from '../models/MissionState';
import type { MissionUpdate } from '../models/MissionUpdate';
import type { PlanRequest } from '../models/PlanRequest';
import type { PlanResponse } from '../models/PlanResponse';
import type { SensorDecisionRequest } from '../models/SensorDecisionRequest';
import type { SensorDecisionResponse } from '../models/SensorDecisionResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ProxyService {
    /**
     * Proxy List Missions
     * Proxy GET /api/v1/missions → Mission service.
     * @returns MissionListResponse Successful Response
     * @throws ApiError
     */
    public static proxyListMissionsApiV1MissionsGet(): CancelablePromise<MissionListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/missions',
        });
    }
    /**
     * Proxy Create Mission
     * Proxy POST /api/v1/missions → Mission service.
     * @param requestBody
     * @returns MissionResponse Successful Response
     * @throws ApiError
     */
    public static proxyCreateMissionApiV1MissionsPost(
        requestBody: MissionCreate,
    ): CancelablePromise<MissionResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/missions',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Get Mission
     * Proxy GET /api/v1/missions/{id} → Mission service.
     * @param missionId
     * @returns MissionResponse Successful Response
     * @throws ApiError
     */
    public static proxyGetMissionApiV1MissionsMissionIdGet(
        missionId: string,
    ): CancelablePromise<MissionResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/missions/{mission_id}',
            path: {
                'mission_id': missionId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Update Mission
     * Proxy PATCH /api/v1/missions/{id} → Mission service.
     * @param missionId
     * @param requestBody
     * @returns MissionResponse Successful Response
     * @throws ApiError
     */
    public static proxyUpdateMissionApiV1MissionsMissionIdPatch(
        missionId: string,
        requestBody: MissionUpdate,
    ): CancelablePromise<MissionResponse> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/v1/missions/{mission_id}',
            path: {
                'mission_id': missionId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Delete Mission
     * Proxy DELETE /api/v1/missions/{id} → Mission service (OPERATOR+).
     * @param missionId
     * @returns void
     * @throws ApiError
     */
    public static proxyDeleteMissionApiV1MissionsMissionIdDelete(
        missionId: string,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/missions/{mission_id}',
            path: {
                'mission_id': missionId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Submit Run
     * Proxy POST /api/v1/missions/{id}/runs → Mission service (OPERATOR+).
     * @param missionId
     * @returns JobSubmitResponse Successful Response
     * @throws ApiError
     */
    public static proxySubmitRunApiV1MissionsMissionIdRunsPost(
        missionId: string,
    ): CancelablePromise<JobSubmitResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/missions/{mission_id}/runs',
            path: {
                'mission_id': missionId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Get Job
     * Proxy GET /api/v1/jobs/{job_id} → Mission service.
     * @param jobId
     * @returns JobStatusResponse Successful Response
     * @throws ApiError
     */
    public static proxyGetJobApiV1JobsJobIdGet(
        jobId: string,
    ): CancelablePromise<JobStatusResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/jobs/{job_id}',
            path: {
                'job_id': jobId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Agent Plan
     * Proxy POST /api/v1/agent/plan → Agent service (ANALYST+).
     * @param requestBody
     * @returns PlanResponse Successful Response
     * @throws ApiError
     */
    public static proxyAgentPlanApiV1AgentPlanPost(
        requestBody: PlanRequest,
    ): CancelablePromise<PlanResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/agent/plan',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Agent Execute
     * Proxy POST /api/v1/agent/execute → Agent service (ANALYST+).
     * @param requestBody
     * @returns ExecuteResponse Successful Response
     * @throws ApiError
     */
    public static proxyAgentExecuteApiV1AgentExecutePost(
        requestBody: ExecuteRequest,
    ): CancelablePromise<ExecuteResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/agent/execute',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Agent Run Status
     * Proxy GET /api/v1/agent/runs/{job_id} → Agent service.
     * @param jobId
     * @returns MissionState Successful Response
     * @throws ApiError
     */
    public static proxyAgentRunStatusApiV1AgentRunsJobIdGet(
        jobId: string,
    ): CancelablePromise<MissionState> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/agent/runs/{job_id}',
            path: {
                'job_id': jobId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Agent Sensor Decision
     * Proxy POST /api/v1/agent/sensor-decision → Agent service.
     * @param requestBody
     * @returns SensorDecisionResponse Successful Response
     * @throws ApiError
     */
    public static proxyAgentSensorDecisionApiV1AgentSensorDecisionPost(
        requestBody: SensorDecisionRequest,
    ): CancelablePromise<SensorDecisionResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/agent/sensor-decision',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Agent Confidence
     * Proxy POST /api/v1/agent/confidence → Agent service.
     * @param requestBody
     * @returns ConfidenceResponse Successful Response
     * @throws ApiError
     */
    public static proxyAgentConfidenceApiV1AgentConfidencePost(
        requestBody: ConfidenceRequest,
    ): CancelablePromise<ConfidenceResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/agent/confidence',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Proxy Agent Tools
     * Proxy GET /api/v1/agent/tools → Agent service.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static proxyAgentToolsApiV1AgentToolsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/agent/tools',
        });
    }
}
