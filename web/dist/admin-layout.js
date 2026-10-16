export function installAdminLayout(root) {
    const sections = Array.from(root.querySelectorAll(":scope > section"));
    const form = sections.find(s => s.dataset.accountEditor === 'true'), accounts = sections.find(s => s.dataset.accountList === 'true'), audit = sections.find(s => s.dataset.legacyAudit === 'true'), credits = sections.find(s => s.querySelector("#credit-form")), collection = sections.find(s => s.dataset.collectionMonitor === "true");
    const workspace = document.createElement("div");
    workspace.className = "admin-workspace";
    const sidebar = document.createElement("aside");
    sidebar.className = "admin-sidebar";
    const items = [["accounts", "Quản lý tài khoản"], ["credits", "Quản lý credits"], ["collection", "Nhật ký hệ thống"]];
    const registration = sections.find(s => s.dataset.registrationReview === "true");
    const aiConfiguration = sections.find(s => s.dataset.analysisConfiguration === 'true');
    if (aiConfiguration)
        items.splice(2, 0, ['ai-configuration', 'Cấu hình phân tích AI']);
    const formulas = sections.find(s => s.dataset.formulaConfiguration === 'true');
    if (formulas)
        items.push(['formulas', 'Công thức tính']);
    const trivia = sections.find(s => s.dataset.triviaBank === 'true');
    const sourceMonitor = sections.find(s => s.dataset.sourceMonitor === 'true');
    const systemNotices = sections.find(s => s.dataset.systemNoticeAdmin === 'true');
    if (systemNotices)
        items.splice(2, 0, ['system-notices', 'Thông báo hệ thống']);
    if (trivia)
        items.push(['trivia', 'Hỏi đáp nhanh']);
    if (registration)
        items.splice(2, 0, ["registrations", "Đăng ký chờ duyệt"]);
    sidebar.innerHTML = `<a class="admin-brand" href="/"><span class="admin-logo"><img class="cchc-logo" src="/assets/logo-cchc.png" alt="Cải cách hành chính" width="44" height="44"></span> <span>Quản trị</span></a><nav aria-label="Quản trị">${items.map(([key, label]) => `<button data-admin-section="${key}">${label}</button>`).join("")}</nav><a class="button admin-back" href="/">Về Tổng quan</a>`;
    const panels = {};
    items.forEach(([key]) => { const panel = document.createElement("div"); panel.dataset.adminPanel = key; panel.hidden = true; panels[key] = panel; workspace.append(panel); });
    panels.accounts.append(form, accounts);
    form.hidden = true;
    if (registration)
        panels.registrations.append(registration);
    const logViews = {};
    for (const section of sections)
        if (section.dataset.logView)
            logViews[section.dataset.logView] = section;
    if (sourceMonitor) {
        sourceMonitor.dataset.logView = 'source';
        logViews.source = sourceMonitor;
    }
    if (!logViews.audit)
        logViews.audit = audit;
    if (collection && !logViews.today)
        logViews.today = collection;
    const logPanel = panels.collection;
    logPanel.classList.add('admin-log-hub');
    const submenus = document.createElement('nav');
    submenus.className = 'log-tabs';
    submenus.setAttribute('aria-label', 'Nhật ký hệ thống');
    submenus.innerHTML = [['today', 'Tổng quan hôm nay'], ['history', 'Lịch sử khai thác'], ['source', 'Cảnh báo nguồn'], ['audit', 'Nhật ký quản trị']].filter(([key]) => logViews[key]).map(([key, label]) => `<button type="button" data-log-tab="${key}" aria-pressed="${key === 'today'}">${label}${key === 'source' ? '<span data-source-count hidden></span>' : ''}</button>`).join('');
    logPanel.append(submenus, ...Object.values(logViews));
    let currentLogView = 'today';
    function selectLog(key) {
        if (!logViews[key])
            return;
        currentLogView = key;
        Object.entries(logViews).forEach(([id, view]) => view.hidden = id !== key);
        submenus.querySelectorAll('[data-log-tab]').forEach(button => { const active = button.dataset.logTab === key; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
        if (!logPanel.hidden)
            root.dispatchEvent(new CustomEvent('qd766-log-view', { detail: key }));
    }
    submenus.addEventListener('click', event => { const button = event.target.closest('[data-log-tab]'); if (button)
        selectLog(button.dataset.logTab); });
    root.addEventListener('qd766-source-count', event => { const count = Number(event.detail), badge = submenus.querySelector('[data-source-count]'); if (badge) {
        badge.hidden = count <= 0;
        badge.textContent = String(count);
    } });
    selectLog(currentLogView);
    if (aiConfiguration)
        panels['ai-configuration'].append(aiConfiguration);
    if (formulas)
        panels.formulas.append(formulas);
    if (trivia)
        panels.trivia.append(trivia);
    if (systemNotices)
        panels['system-notices'].append(systemNotices);
    if (credits)
        panels.credits.append(credits);
    else
        panels.credits.innerHTML = "<section><h2>Quản lý credits</h2><p>Chức năng cấp credit chưa được mở ở môi trường này.</p></section>";
    const header = root.querySelector("header"), message = root.querySelector("#message");
    if (header)
        workspace.prepend(header);
    if (message)
        workspace.insertBefore(message, workspace.children[1] ?? null);
    root.append(sidebar, workspace);
    root.classList.add("admin-shell");
    const select = (key) => { Object.entries(panels).forEach(([id, panel]) => panel.hidden = id !== key); sidebar.querySelectorAll("button").forEach(button => { const active = button.dataset.adminSection === key; button.classList.toggle("active", active); button.setAttribute("aria-current", active ? "page" : "false"); }); root.dispatchEvent(new CustomEvent('qd766-admin-section', { detail: key })); };
    sidebar.querySelectorAll("button").forEach(button => button.addEventListener("click", () => {
        select(button.dataset.adminSection);
        if (button.dataset.adminSection === 'collection')
            selectLog(currentLogView);
    }));
    select("accounts");
    return { credits: () => select("credits"), edit: () => { form.hidden = false; select("accounts"); }, closeEdit: () => { form.hidden = true; select("accounts"); } };
}
//# sourceMappingURL=admin-layout.js.map