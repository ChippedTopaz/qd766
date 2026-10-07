const esc = (v) => v.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function triviaDeleteMarkup(q) {
    return `<h2 id="trivia-delete-title">Xóa câu hỏi?</h2><p class="trivia-delete-question">${esc(q.prompt)}</p><p>Câu hỏi và toàn bộ lịch sử trả lời câu này sẽ bị xóa vĩnh viễn, kể cả các lượt làm lại.</p><p>Điểm, chuỗi đúng và kỷ lục của người đã trả lời được tính lại, loại bỏ đóng góp của câu này. Không ảnh hưởng Credit. Nếu chỉ muốn ngừng hiển thị, hãy chọn <strong>Thu hồi</strong> thay vì Xóa.</p><label class="trivia-delete-ack"><input type="checkbox" data-delete-ack>Tôi xác nhận xóa câu hỏi và lịch sử trả lời.</label><p data-delete-status role="status"></p><div class="actions"><button type="button" data-delete-cancel>Hủy</button><button type="button" class="trivia-danger" data-delete-confirm disabled>Xóa vĩnh viễn</button></div>`;
}
export function confirmTriviaDeletion(q, api) {
    return new Promise(resolve => {
        const dialog = document.createElement('dialog');
        dialog.className = 'trivia-delete-dialog';
        dialog.setAttribute('aria-labelledby', 'trivia-delete-title');
        dialog.innerHTML = triviaDeleteMarkup(q);
        const ack = dialog.querySelector('[data-delete-ack]'), confirm = dialog.querySelector('[data-delete-confirm]'), cancel = dialog.querySelector('[data-delete-cancel]');
        let busy = false, deleted = false;
        ack.addEventListener('change', () => { confirm.disabled = !ack.checked || busy; });
        cancel.addEventListener('click', () => { if (!busy)
            dialog.close(); });
        dialog.addEventListener('cancel', event => { if (busy)
            event.preventDefault(); });
        dialog.addEventListener('close', () => { dialog.remove(); resolve(deleted); }, { once: true });
        confirm.addEventListener('click', async () => {
            if (busy || !ack.checked)
                return;
            busy = true;
            confirm.disabled = cancel.disabled = ack.disabled = true;
            const status = dialog.querySelector('[data-delete-status]');
            status.textContent = 'Đang xóa và tính lại điểm…';
            try {
                await api(`admin/trivia/${encodeURIComponent(q.id)}/delete`, { revision: q.revision, confirm: true });
                deleted = true;
                dialog.close();
            }
            catch (error) {
                status.textContent = error.message;
                busy = false;
                cancel.disabled = ack.disabled = false;
                confirm.disabled = !ack.checked;
            }
        });
        document.body.append(dialog);
        dialog.showModal();
        cancel.focus();
    });
}
//# sourceMappingURL=admin-trivia-delete.js.map