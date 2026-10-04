export function insufficientCreditMessage(totalCredits, availableCredits) {
    return totalCredits > availableCredits ? "Tài khoản của bạn không đủ Credit để thực hiện lượt tra cứu này." : null;
}
export function collectionCopy(items) {
    const allOwned = items.length > 0 && items.every(item => item.owned);
    if (allOwned && items.every(item => item.ownedState === "ready"))
        return {
            title: "Dữ liệu đã có trong thư viện", notice: "Bạn đã khai thác dữ liệu này trong kỳ đang chọn. Có thể xem lại mà không phát sinh Credit.",
            button: items.length === 1 ? "Xem dữ liệu" : "Xem thư viện", mode: "ready"
        };
    if (allOwned)
        return { title: "Yêu cầu đã được tiếp nhận",
            notice: "Bạn đã gửi yêu cầu khai thác dữ liệu này. Hệ thống sẽ thông báo khi dữ liệu sẵn sàng. Không tạo yêu cầu trùng hoặc giữ thêm Credit.",
            button: "Xem yêu cầu", mode: "waiting" };
    const hasOwned = items.some(item => item.owned);
    return { title: "Tra cứu dữ liệu", notice: (hasOwned ? "Các thủ tục đã thuộc thư viện hoặc có yêu cầu đang xử lý không phát sinh thêm Credit. " : "") +
            "Credit được giữ khi xác nhận và chỉ ghi nhận thu khi dữ liệu sẵn sàng. Yêu cầu thất bại, bị chặn hoặc hủy sẽ được hoàn toàn bộ Credit.",
        button: "Tra cứu dữ liệu", mode: "new" };
}
//# sourceMappingURL=collection-copy.js.map