const GROUPS = [['transparency', 'Công khai, minh bạch', '#2563eb'], ['dvc-progress-tree', 'Tiến độ giải quyết', '#059669'], ['provide-online-tree', 'Dịch vụ công trực tuyến', '#ec4899'], ['dossier-digitized', 'Số hóa hồ sơ', '#8b5cf6'], ['handling-satisfaction', 'Mức độ hài lòng', '#d97706'], ['formality-online-payment-tree', 'Thanh toán trực tuyến', '#0891b2']];
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function installAnalysisConfiguration(root, api) {
    const section = document.createElement('section');
    section.dataset.analysisConfiguration = 'true';
    section.innerHTML = `<h2>Cấu hình phân tích AI</h2><p>Hướng dẫn và kiến thức riêng cho từng nhóm chỉ tiêu. Người dùng chọn nhóm cần phân tích, 5 Credit mỗi nhóm; mỗi nhóm được gửi với ngữ cảnh riêng.</p><div class="ai-config-groups" role="group" aria-label="Nhóm chỉ tiêu">${GROUPS.map(([id, label, color]) => `<button type="button" data-ai-config-group="${id}" style="--group-color:${color}" aria-pressed="false">${label}<span data-ai-draft="${id}" hidden> · Chưa lưu</span></button>`).join('')}</div><p id="ai-config-status" role="status">Mở mục này để tải cấu hình.</p><form id="ai-config-form"><h3 id="ai-config-group-title"></h3><label>Hướng dẫn phân tích<textarea id="ai-config-guidance" rows="6" minlength="20" maxlength="4000" required placeholder="Cách nhận định, ưu tiên và khuyến nghị riêng cho nhóm này…"></textarea></label><label>Kiến thức nghiệp vụ đã duyệt<textarea id="ai-config-knowledge" rows="8" maxlength="10000" placeholder="Công thức, điều kiện áp dụng, ngoại lệ và ví dụ của riêng nhóm này. Ghi nguồn và ngày đối chiếu nếu có."></textarea></label><p class="ai-config-hint">Không nhập khóa API, mật khẩu hoặc dữ liệu cá nhân. Kiến thức Gemini web không tự đồng bộ. Lưu chỉ áp dụng cho nhóm đang chọn; bản nháp của nhóm khác được giữ trong tab này.</p><label>Ghi chú thay đổi<input id="ai-config-note" minlength="3" maxlength="500" required placeholder="Nội dung sửa đổi của nhóm đang chọn"></label><div class="actions"><button class="primary" id="ai-config-save" disabled>Lưu nhóm đang chọn</button><button type="button" id="ai-config-default" disabled>Đưa mặc định nhóm vào bản nháp</button><button type="button" id="ai-config-reload">Tải lại cấu hình</button></div></form><details class="ai-config-legacy" hidden><summary>Cấu hình chung cũ — chỉ đọc</summary><p>Cấu hình cũ được giữ để đối chiếu, không tự sao chép vào các nhóm. Lượt mới dùng hướng dẫn riêng theo nhóm; nhóm chưa cấu hình dùng mặc định riêng. Lượt đang chờ và kết quả cũ không đổi.</p><pre id="ai-config-legacy-guidance"></pre><pre id="ai-config-legacy-knowledge"></pre></details><details class="ai-config-rules"><summary>Nguyên tắc hệ thống</summary><ul id="ai-config-rules"></ul><p>API key, model, mức Credit và hàng chờ không được chỉnh bằng nội dung hướng dẫn.</p></details><div class="ai-config-history"><h3>Lịch sử phiên bản</h3><label>Phiên bản đã lưu<select id="ai-config-version" disabled></select></label><button type="button" id="ai-config-load-version" disabled>Đưa nhóm trong phiên bản vào bản nháp</button><p>Chỉ khôi phục bản nháp của nhóm đang chọn. Bấm Lưu mới áp dụng; các phiên bản đã lưu được giữ lại.</p></div>`;
    root.append(section);
    const control = document.createElement('div');
    control.className = 'ai-feature-control';
    control.innerHTML = '<div><strong>Phân tích điểm số</strong><p id="ai-feature-status" role="status">Chưa tải trạng thái.</p></div><button type="button" id="ai-feature-toggle" role="switch" aria-checked="false" disabled>Bật / tắt</button><p class="ai-feature-hint">Tắt sẽ chặn lượt mới trước khi giữ Credit. Lượt đang xử lý được hoàn tất; lượt chờ được hoàn Credit khi worker xử lý. Kết quả đã lưu và bản nháp cấu hình được giữ nguyên.</p>';
    section.querySelector('h2').after(control);
    const get = (id) => section.querySelector('#' + id);
    const status = (text) => { get('ai-config-status').textContent = text; };
    const drafts = new Map();
    let selected = GROUPS[0][0], configuration = null, busy = false, loaded = false;
    const setBusy = (value) => {
        busy = value;
        section.setAttribute('aria-busy', String(value));
        ['save', 'default', 'load-version'].forEach(name => { get('ai-config-' + name).disabled = value || !configuration || (name === 'save' && !configuration.groupSchemaReady); });
        get('ai-config-reload').disabled = value;
        get('ai-feature-toggle').disabled = value || !configuration?.feature?.schemaReady;
        get('ai-config-version').disabled = value || !configuration;
        ['ai-config-guidance', 'ai-config-knowledge', 'ai-config-note'].forEach(id => get(id).disabled = value || !configuration);
        section.querySelectorAll('[data-ai-config-group]').forEach(button => button.disabled = value || !configuration);
    };
    const showFeature = () => {
        const feature = configuration?.feature, button = get('ai-feature-toggle');
        button.setAttribute('aria-checked', String(!!feature?.enabled));
        button.textContent = feature?.enabled ? 'Đang bật · Tắt tính năng' : 'Đang tắt · Bật tính năng';
        get('ai-feature-status').textContent = !feature?.schemaReady ? 'Cần cập nhật schema trước khi sử dụng nút bật/tắt.' : feature.enabled ? 'Đang cho phép lượt phân tích mới.' : 'Tính năng tạm thời không khả dụng do đang trong quá trình nâng cấp.';
    };
    const markDrafts = () => section.querySelectorAll('[data-ai-draft]').forEach(marker => marker.hidden = !drafts.has(marker.dataset.aiDraft));
    const remember = () => {
        if (!configuration)
            return;
        const value = { guidance: get('ai-config-guidance').value, knowledge: get('ai-config-knowledge').value, note: get('ai-config-note').value };
        const saved = configuration.groups[selected];
        if (value.guidance === saved.guidance && value.knowledge === saved.knowledge && !value.note)
            drafts.delete(selected);
        else
            drafts.set(selected, value);
        markDrafts();
    };
    const showGroup = () => {
        const value = drafts.get(selected) ?? configuration?.groups[selected];
        if (!value)
            return;
        get('ai-config-guidance').value = value.guidance;
        get('ai-config-knowledge').value = value.knowledge;
        get('ai-config-note').value = drafts.get(selected)?.note ?? '';
        get('ai-config-group-title').textContent = GROUPS.find(([key]) => key === selected)[1];
        section.querySelectorAll('[data-ai-config-group]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.aiConfigGroup === selected)));
        markDrafts();
    };
    const fill = (value) => {
        configuration = value;
        loaded = true;
        showGroup();
        showFeature();
        get('ai-config-rules').innerHTML = value.rules.map(rule => `<li>${esc(rule)}</li>`).join('');
        get('ai-config-version').innerHTML = value.history.map(row => `<option value="${row.version}">Phiên bản ${row.version} · ${esc(new Date(row.at).toLocaleString('vi-VN'))} · ${esc(row.actor)} · ${esc(row.note)}</option>`).join('') + '<option value="0">Mặc định hệ thống</option>';
        get('ai-config-version').value = String(value.version);
        section.querySelector('.ai-config-legacy').hidden = !value.legacyConfiguration;
        get('ai-config-legacy-guidance').textContent = value.legacyConfiguration?.guidance ?? '';
        get('ai-config-legacy-knowledge').textContent = value.legacyConfiguration?.knowledge ?? '';
        status(value.groupSchemaReady ? `Phiên bản áp dụng: ${value.activeVersion}. Chỉ lưu nhóm đang chọn.` : 'Cần nâng schema cấu hình theo nhóm trước khi lưu. Cấu hình hiện tại được giữ nguyên.');
    };
    const load = async () => {
        if (busy)
            return;
        setBusy(true);
        status('Đang tải cấu hình…');
        try {
            remember();
            fill(await api('admin/analysis-configuration'));
        }
        catch (error) {
            status(error instanceof Error ? error.message : 'Không tải được cấu hình.');
        }
        finally {
            setBusy(false);
        }
    };
    root.addEventListener('click', event => { const key = event.target.closest('[data-admin-section]')?.dataset.adminSection; if (key === 'ai-configuration' && !loaded)
        void load(); });
    section.addEventListener('click', event => {
        const key = event.target.closest('[data-ai-config-group]')?.dataset.aiConfigGroup;
        if (busy || !configuration || !key || !GROUPS.some(([id]) => id === key))
            return;
        remember();
        selected = key;
        showGroup();
    });
    ['ai-config-guidance', 'ai-config-knowledge', 'ai-config-note'].forEach(id => get(id).addEventListener('input', remember));
    get('ai-config-reload').addEventListener('click', () => void load());
    get('ai-feature-toggle').addEventListener('click', () => {
        if (busy || !configuration?.feature?.schemaReady)
            return;
        const payload = { enabled: !configuration.feature.enabled, expectedRevision: configuration.feature.revision };
        void (async () => {
            setBusy(true);
            try {
                configuration.feature = await api('admin/analysis-configuration/feature', payload);
                showFeature();
            }
            catch (error) {
                get('ai-feature-status').textContent = error instanceof Error ? error.message : 'Chưa xác nhận được trạng thái. Tải lại cấu hình trước khi thử lại.';
            }
            finally {
                setBusy(false);
            }
        })();
    });
    get('ai-config-default').addEventListener('click', () => {
        if (busy || !configuration)
            return;
        drafts.set(selected, { ...configuration.defaultGroups[selected], note: 'Khôi phục mặc định nhóm' });
        showGroup();
        status('Đã đưa mặc định nhóm vào bản nháp. Chưa thay đổi cấu hình đang áp dụng.');
    });
    get('ai-config-load-version').addEventListener('click', () => {
        if (busy || !configuration)
            return;
        setBusy(true);
        void (async () => {
            try {
                const value = await api('admin/analysis-configuration?version=' + Number(get('ai-config-version').value));
                drafts.set(selected, { ...value.groups[selected], note: `Khôi phục nhóm từ phiên bản ${value.version}` });
                showGroup();
                section.querySelector('.ai-config-legacy').hidden = !value.legacyConfiguration;
                get('ai-config-legacy-guidance').textContent = value.legacyConfiguration?.guidance ?? '';
                get('ai-config-legacy-knowledge').textContent = value.legacyConfiguration?.knowledge ?? '';
                status(`Đã đưa nhóm từ phiên bản ${value.version} vào bản nháp. Chưa áp dụng.`);
            }
            catch (error) {
                status(error instanceof Error ? error.message : 'Không tải được phiên bản.');
            }
            finally {
                setBusy(false);
            }
        })();
    });
    get('ai-config-form').addEventListener('submit', event => {
        event.preventDefault();
        if (busy || !configuration?.groupSchemaReady)
            return;
        remember();
        const savedGroup = selected;
        const payload = { expectedVersion: configuration.activeVersion, groupId: savedGroup, guidance: get('ai-config-guidance').value, knowledge: get('ai-config-knowledge').value, note: get('ai-config-note').value };
        void (async () => {
            setBusy(true);
            status('Đang lưu nhóm…');
            try {
                const result = await api('admin/analysis-configuration', payload);
                configuration.activeVersion = result.version;
                configuration.groups[savedGroup] = { guidance: payload.guidance, knowledge: payload.knowledge };
                drafts.delete(savedGroup);
                showGroup();
                fill(await api('admin/analysis-configuration'));
                status(`Đã lưu nhóm trong phiên bản ${result.version}. Áp dụng cho lượt xác nhận mới; nhóm khác không đổi.`);
            }
            catch (error) {
                status(error instanceof Error ? error.message : 'Chưa xác nhận được kết quả lưu. Tải lại trước khi gửi lại.');
            }
            finally {
                setBusy(false);
            }
        })();
    });
    setBusy(false);
}
//# sourceMappingURL=admin-analysis-configuration.js.map