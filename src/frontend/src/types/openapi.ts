// Generated from W0 OpenAPI v1. Do not edit.
export interface paths {
    "/api/v1/datasets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["DatasetList"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["RunAccepted"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["RunStatus"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["SeriesPage"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/alarms": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["SeriesPageAlarms"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/evaluation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["Evaluation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/minutes/{timestamp}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["MinuteDetail"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/exports/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["ExportRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** RunRequest */
        RunRequest: {
            /** Dataset Id */
            dataset_id: string;
            /** Split Id */
            split_id: string;
            /**
             * Method
             * @enum {string}
             */
            method: "iforest" | "current_ae" | "history_ae";
            /** Config Id */
            config_id: string;
        };
        /** RunAccepted */
        RunAccepted: {
            /** Run Id */
            run_id: string;
            /**
             * Status
             * @constant
             */
            status: "queued";
        };
        /** ErrorDetail */
        ErrorDetail: {
            /**
             * Code
             * @enum {string}
             */
            code: "RUN_BUSY" | "WORKER_INTERRUPTED" | "NOT_FOUND" | "VALIDATION_ERROR" | "RESULT_NOT_READY" | "EXECUTION_FAILED";
            /** Message */
            message: string;
            /** Details */
            details?: string[];
        };
        /** ModelConfig */
        ModelConfig: {
            /** Hidden Widths */
            hidden_widths?: number[];
            /**
             * Epochs
             * @default 10
             */
            epochs: number;
            /**
             * Batch Size
             * @default 128
             */
            batch_size: number;
            /**
             * Learning Rate
             * @default 0.001
             */
            learning_rate: number;
            /**
             * N Estimators
             * @default 100
             */
            n_estimators: number;
            /**
             * Max Samples
             * @default 256
             */
            max_samples: number;
        };
        /** PreprocessConfig */
        PreprocessConfig: {
            /**
             * Version
             * @default log1p-standard-v1
             * @constant
             */
            version: "log1p-standard-v1";
            /**
             * Epsilon
             * @default 0.000001
             */
            epsilon: number;
            /**
             * Quantile
             * @default 0.99
             * @constant
             */
            quantile: 0.99;
            /**
             * Quantile Method
             * @default linear
             * @constant
             */
            quantile_method: "linear";
        };
        /** RunConfig */
        RunConfig: {
            /**
             * Schema Version
             * @default 1.0
             * @constant
             */
            schema_version: "1.0";
            /** Dataset Id */
            dataset_id: string;
            /** Split Id */
            split_id: string;
            /**
             * Method
             * @enum {string}
             */
            method: "iforest" | "current_ae" | "history_ae";
            /**
             * Window Minutes
             * @default 15
             */
            window_minutes: number;
            /**
             * Seed
             * @default 42
             */
            seed: number;
            preprocess?: components["schemas"]["PreprocessConfig"];
            model?: components["schemas"]["ModelConfig"];
        };
        /** RunStatus */
        RunStatus: {
            /** Run Id */
            run_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed";
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            config: components["schemas"]["RunConfig"];
            error: components["schemas"]["ErrorDetail"] | null;
        };
        /** DatasetInfo */
        DatasetInfo: {
            /** Dataset Id */
            dataset_id: string;
            /** Version */
            version: string;
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            /** Available */
            available: boolean;
            /** Unavailable Reason */
            unavailable_reason: string | null;
            time_range: components["schemas"]["TimeRange"] | null;
            /**
             * Feature Count
             * @constant
             */
            feature_count: 134;
            /** Split Ids */
            split_ids: string[];
            /** Config Ids */
            config_ids: string[];
        };
        /** TimeRange */
        TimeRange: {
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /**
             * End
             * Format: date-time
             */
            end: string;
        };
        /** DatasetList */
        DatasetList: {
            /** Items */
            items: components["schemas"]["DatasetInfo"][];
        };
        /** SeriesPoint */
        SeriesPoint: {
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
            /** Score */
            score: number | null;
            /** Threshold */
            threshold: number | null;
            /** Alarm */
            alarm: boolean | null;
            /** Valid */
            valid: boolean;
            /** Invalid Reason */
            invalid_reason: ("warmup" | "gap" | "invalid_input" | "not_common" | "nonfinite_score") | null;
            /** Flow Count */
            flow_count: number | null;
        };
        /** SeriesPage */
        SeriesPage: {
            /** Run Id */
            run_id: string;
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            /** Items */
            items: components["schemas"]["SeriesPoint"][];
            /** Total */
            total: number;
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
        };
        /** Coverage */
        Coverage: {
            /** Eligible */
            eligible: number;
            /** Total */
            total: number;
        };
        /** EvaluationInterval */
        EvaluationInterval: {
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /**
             * End
             * Format: date-time
             */
            end: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "false_positive" | "missed_attack";
            /** Minute Count */
            minute_count: number;
        };
        /** Metrics */
        Metrics: {
            /** Tp */
            tp: number;
            /** Fp */
            fp: number;
            /** Tn */
            tn: number;
            /** Fn */
            fn: number;
            /** Precision */
            precision: number | null;
            /** Recall */
            recall: number | null;
            /** F1 */
            f1: number | null;
            /** Fpr */
            fpr: number | null;
            /** Undefined Reasons */
            undefined_reasons: string[];
        };
        /** Evaluation */
        Evaluation: {
            /** Run Id */
            run_id: string;
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            /** Available */
            available: boolean;
            /** Reason */
            reason: string | null;
            metrics: components["schemas"]["Metrics"] | null;
            normal_coverage: components["schemas"]["Coverage"];
            attack_coverage: components["schemas"]["Coverage"];
            /** Excluded Attack Minutes */
            excluded_attack_minutes: number;
            /** Background Only Minutes */
            background_only_minutes: number;
            /** Intervals */
            intervals: components["schemas"]["EvaluationInterval"][];
            high_load_metrics: components["schemas"]["Metrics"] | null;
            /** High Load Unavailable Reason */
            high_load_unavailable_reason: string | null;
        };
        /** MinuteDetail */
        MinuteDetail: {
            /** Current */
            current: number[] | null;
            /** History Residual */
            history_residual: number[] | null;
            /** Reconstruction Error Current */
            reconstruction_error_current: number[] | null;
            /** Reconstruction Error History */
            reconstruction_error_history: number[] | null;
            /** Run Id */
            run_id: string;
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            point: components["schemas"]["SeriesPoint"];
            /** Feature Names */
            feature_names: string[];
            /** Labels */
            labels: {
                [key: string]: number;
            } | null;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ErrorDetail"];
        };
        /** ArtifactFile */
        ArtifactFile: {
            /** Path */
            path: string;
            /** Sha256 */
            sha256: string;
        };
        /** Manifest */
        Manifest: {
            /**
             * Schema Version
             * @default 1.0
             * @constant
             */
            schema_version: "1.0";
            /** Run Id */
            run_id: string;
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            config: components["schemas"]["RunConfig"];
            /** Code Commit */
            code_commit: string;
            /** Dataset Version */
            dataset_version: string;
            /** Feature Version */
            feature_version: string;
            /** Split Version */
            split_version: string;
            /** Seed */
            seed: number;
            /** Dependency Lock Sha256 */
            dependency_lock_sha256: string;
            /** Files */
            files: components["schemas"]["ArtifactFile"][];
        };
        /** RunResult */
        RunResult: {
            /** Run Id */
            run_id: string;
            /** Manifest Path */
            manifest_path: string;
            /** Summary Path */
            summary_path: string;
            /** Scores Path */
            scores_path: string;
        };
        /** DatasetSchema */
        DatasetSchema: {
            /**
             * Schema Version
             * @default 1.0
             * @constant
             */
            schema_version: "1.0";
            /** Dataset Id */
            dataset_id: string;
            /** Dataset Version */
            dataset_version: string;
            /** Feature Names */
            feature_names: string[];
            /** Source Timezone */
            source_timezone: string;
            /** Time Basis Source */
            time_basis_source: string;
            /**
             * Label Names
             * @default [
             *       "dos",
             *       "scan11",
             *       "scan44",
             *       "botnet",
             *       "blacklist",
             *       "udpscan",
             *       "sshscan",
             *       "spam"
             *     ]
             */
            label_names: string[];
        };
        /** SplitBoundaries */
        SplitBoundaries: {
            /** Split Id */
            split_id: string;
            train: components["schemas"]["TimeRange"];
            validation: components["schemas"]["TimeRange"];
            calibration: components["schemas"]["TimeRange"];
            test: components["schemas"]["TimeRange"];
        };
        /** RunSummary */
        RunSummary: {
            /**
             * Schema Version
             * @default 1.0
             * @constant
             */
            schema_version: "1.0";
            /** Run Id */
            run_id: string;
            /**
             * Evidence Kind
             * @enum {string}
             */
            evidence_kind: "SYNTHETIC_ONLY" | "REAL_DATA";
            config: components["schemas"]["RunConfig"];
            /** Feature Names */
            feature_names: string[];
            /** Row Count */
            row_count: number;
            /** Valid Count */
            valid_count: number;
            /** Elapsed Seconds */
            elapsed_seconds: number;
            /** Peak Memory Bytes */
            peak_memory_bytes: number;
            /** Labels Available */
            labels_available: boolean;
        };
        /** ChannelRow */
        ChannelRow: {
            /** Current */
            current: number[] | null;
            /** History Residual */
            history_residual: number[] | null;
            /** Reconstruction Error Current */
            reconstruction_error_current: number[] | null;
            /** Reconstruction Error History */
            reconstruction_error_history: number[] | null;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        /** LabelRow */
        LabelRow: {
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
            /** Dos */
            dos: number;
            /** Scan11 */
            scan11: number;
            /** Scan44 */
            scan44: number;
            /** Botnet */
            botnet: number;
            /** Blacklist */
            blacklist: number;
            /** Udpscan */
            udpscan: number;
            /** Sshscan */
            sshscan: number;
            /** Spam */
            spam: number;
        };
        /** ModelMetadata */
        ModelMetadata: {
            /**
             * Schema Version
             * @default 1.0
             * @constant
             */
            schema_version: "1.0";
            /**
             * Method
             * @enum {string}
             */
            method: "iforest" | "current_ae" | "history_ae";
            /**
             * Input Width
             * @enum {integer}
             */
            input_width: 134 | 268;
            /** Feature Names */
            feature_names: string[];
            /**
             * Preprocess Version
             * @constant
             */
            preprocess_version: "log1p-standard-v1";
            /** Threshold */
            threshold: number;
            /** Parameter Count */
            parameter_count: number;
            payload: components["schemas"]["ArtifactFile"];
        };
        /** PreprocessState */
        PreprocessState: {
            /**
             * Version
             * @default log1p-standard-v1
             * @constant
             */
            version: "log1p-standard-v1";
            /** Feature Names */
            feature_names: string[];
            /** Mean */
            mean: number[];
            /** Scale */
            scale: number[];
            /** N Samples Seen */
            n_samples_seen: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    DatasetList: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description DatasetList */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DatasetList"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    RunAccepted: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                /**
                 * @example {
                 *       "dataset_id": "synthetic-v1",
                 *       "split_id": "split-v1",
                 *       "method": "iforest",
                 *       "config_id": "smoke-v1"
                 *     }
                 */
                "application/json": components["schemas"]["RunRequest"];
            };
        };
        responses: {
            /** @description RunAccepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunAccepted"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    RunStatus: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description RunStatus */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunStatus"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    SeriesPage: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                start?: string;
                end?: string;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description SeriesPage */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SeriesPage"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    SeriesPageAlarms: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                start?: string;
                end?: string;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description SeriesPage */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SeriesPage"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    Evaluation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Evaluation */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Evaluation"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    MinuteDetail: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
                timestamp: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description MinuteDetail */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MinuteDetail"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    ExportRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
                kind: "scores" | "metrics" | "config";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Complete-minute Parquet scores, or JSON metrics/config. Content-Disposition attachment. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/vnd.apache.parquet": string;
                    "application/json": components["schemas"]["Evaluation"] | components["schemas"]["RunConfig"];
                };
            };
            /** @description ErrorResponse */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description ErrorResponse */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
