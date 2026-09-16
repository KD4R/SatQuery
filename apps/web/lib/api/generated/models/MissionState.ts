/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Canonical MissionState model representing LangGraph / agent state across the workflow.
 */
export type MissionState = {
    /**
     * Unique mission identifier
     */
    mission_id: string;
    /**
     * Execution run identifier
     */
    run_id: string;
    /**
     * Tenant organization identifier
     */
    organization_id: string;
    /**
     * Background job identifier
     */
    job_id?: (string | null);
    /**
     * Distributed trace identifier
     */
    trace_id?: (string | null);
    /**
     * Raw natural language prompt
     */
    query: string;
    /**
     * Sanitized query text
     */
    sanitized_query?: (string | null);
    /**
     * Workflow state: INITIALIZED, PLANNING, ACQUIRING, ANALYZING, GATE_CHECK, COMPLETED, FAILED, CLARIFICATION_REQUIRED
     */
    status?: string;
    /**
     * Extracted mission intent
     */
    intent?: (Record<string, any> | null);
    /**
     * GeoJSON Area of Interest
     */
    aoi?: (Record<string, any> | null);
    /**
     * Temporal comparison window (baseline vs current)
     */
    temporal_window?: (Record<string, any> | null);
    /**
     * List of chosen satellite sensors (e.g. S1_SAR, S2_OPTICAL)
     */
    selected_sensors?: Array<string>;
    /**
     * IDs of selected satellite observations
     */
    observation_ids?: Array<string>;
    /**
     * Audit trail of tool calls executed
     */
    tool_calls?: Array<Record<string, any>>;
    /**
     * Structured DAG of evidence nodes and edges
     */
    evidence_graph?: (Record<string, any> | null);
    /**
     * Overall confidence score [0.0 - 1.0]
     */
    confidence_score?: number;
    /**
     * Explicit reasons for low confidence or uncertainty
     */
    uncertainty_reasons?: Array<string>;
    /**
     * Evidence-backed synthesis and explanations
     */
    synthesized_output?: (Record<string, any> | null);
    /**
     * Encountered errors/warnings
     */
    errors?: Array<string>;
    /**
     * System provenance metadata: dataset_id, model_version, processing_version
     */
    metadata?: Record<string, any>;
    /**
     * Creation timestamp
     */
    created_at?: string;
    /**
     * Last update timestamp
     */
    updated_at?: string;
};

