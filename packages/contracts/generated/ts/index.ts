// Stub for generated API client
// To be replaced by the actual generator when backend contracts are frozen (P5-02)

export interface Mission {
    id: string;
    name: string;
}

export class ApiClient {
    constructor(private baseUrl: string) {}

    async getMissions(): Promise<Mission[]> {
        return [];
    }
}
