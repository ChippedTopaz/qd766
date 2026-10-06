/** Page-local only: no account data in persistent browser storage. */
export class RecentDashboard {
    ttl;
    maximum;
    clock;
    entries = new Map();
    constructor(ttl = 30_000, maximum = 2, clock = () => Date.now()) {
        this.ttl = ttl;
        this.maximum = maximum;
        this.clock = clock;
    }
    get(key) { const entry = this.entries.get(key); if (!entry)
        return; if (entry.expires <= this.clock()) {
        this.entries.delete(key);
        return;
    } this.entries.delete(key); this.entries.set(key, entry); return entry.value; }
    set(key, value) { this.entries.delete(key); this.entries.set(key, { expires: this.clock() + this.ttl, value }); while (this.entries.size > this.maximum)
        this.entries.delete(this.entries.keys().next().value); }
}
//# sourceMappingURL=recent-dashboard.js.map