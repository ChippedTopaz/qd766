export const overviewTabItems = [
    { id: "overview", label: "Tổng quan" },
    { id: "details", label: "Chi tiết điểm số" },
    { id: "analysis", label: "Phân tích - đánh giá" },
];
export function overviewTabs(active) {
    return `<div class="overview-tabs" role="tablist" aria-label="Nội dung tổng quan">${overviewTabItems.map(tab => `<button id="overview-tab-${tab.id}" role="tab" data-overview-tab="${tab.id}" aria-selected="${active === tab.id}" aria-controls="overview-tab-panel" tabindex="${active === tab.id ? 0 : -1}">${tab.label}</button>`).join("")}</div>`;
}
export function adjacentGroup(groups, current, direction) {
    if (!groups.length)
        return null;
    const index = current === null ? -1 : groups.indexOf(current);
    if (index < 0)
        return (direction < 0 ? groups[groups.length - 1] : groups[0]) ?? null;
    return groups[(index + direction + groups.length) % groups.length] ?? null;
}
//# sourceMappingURL=overview-tabs.js.map