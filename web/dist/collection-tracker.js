export class CollectionTracker {
    update;
    read;
    schedule;
    requests = new Map();
    active = new Set();
    constructor(update, read, schedule) {
        this.update = update;
        this.read = read;
        this.schedule = schedule;
    }
    track(request) {
        const id = `${request.kind}:${request.id}`;
        if (this.active.has(id))
            return;
        this.requests.set(id, request);
        this.active.add(id);
        this.update(request, false);
        this.poll(id, 10000);
    }
    hasActive(key) {
        return [...this.active].some(id => this.requests.get(id)?.key === key);
    }
    poll(id, delay) {
        this.schedule(() => { void this.check(id, delay); }, delay);
    }
    async check(id, delay) {
        const request = this.requests.get(id);
        try {
            const endpoint = request.kind === "job" ? "collection-jobs" : "formality-batches";
            const status = await this.read(`/api/v1/${endpoint}/${encodeURIComponent(request.id)}`);
            request.state = status.state;
            const finished = (status.availableItems ?? 0) + (status.completedItems ?? 0);
            request.message = request.kind === "batch" && status.totalItems !== undefined
                ? `Đã hoàn thành ${finished}/${status.totalItems} TTHC.`
                : status.state === "running" ? "Đang lấy và kiểm tra dữ liệu."
                    : status.state === "succeeded" ? "Dữ liệu đã được lưu, sẵn sàng để xem."
                        : "Đang chờ đến lượt xử lý; không cần gửi lại yêu cầu.";
            const terminal = ["succeeded", "failed", "halted", "cancelled", "canceled"].includes(status.state);
            if (terminal) {
                this.active.delete(id);
                if (status.state !== "succeeded")
                    request.message = status.error?.message ?? "Yêu cầu đã dừng; xem mục Vận hành để biết chi tiết.";
            }
            this.update(request, status.state === "succeeded");
            if (!terminal)
                this.poll(id, 10000);
        }
        catch {
            // A status read failure is not evidence that collection failed.
            request.state = "unavailable";
            request.message = "Chưa đọc được tiến độ. Hệ thống sẽ thử đọc lại; không tạo yêu cầu mới.";
            this.update(request, false);
            this.poll(id, Math.min(delay * 2, 60000));
        }
    }
}
//# sourceMappingURL=collection-tracker.js.map