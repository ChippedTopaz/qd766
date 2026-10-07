import { groupIcon, groupColors, icon } from './bento.js';
import { formulaMaximums, maximumText } from './formula-maximums.js';
import { formulaDocument } from './formula-document.js';
export const formulaSource = { name: formulaDocument.name, sha256: formulaDocument.sha256, version: 'Đối chiếu ngày 07/10/2026' };
const formulaDefinitions = [
    { id: 'transparency', name: 'Công khai, minh bạch', maximum: 18, items: [
            { id: '1.1', numerator: 'TTHC công bố đúng hạn', denominator: 'TTHC đã công bố trong kỳ' },
            { id: '1.2', numerator: 'TTHC công khai đúng hạn trên CSDL quốc gia', denominator: 'TTHC phải cập nhật, công khai trong kỳ', caution: 'Điều kiện “Ngày QĐ ≤ ngày cuối kỳ + 10/5 ngày làm việc” trong tài liệu cần được làm rõ trước khi tự tái dựng danh sách hồ sơ.' },
            { id: '1.3', numerator: 'TTHC đầy đủ các bộ phận cấu thành', denominator: 'TTHC đã cập nhật, công khai trên CSDL quốc gia', caution: 'Tài liệu nêu không tính theo thời gian nhưng phần lưu ý chung lại ghi theo kỳ. Trang này giữ quy tắc nghiệp vụ cụ thể và ghi nhận khác biệt.' },
            { id: '1.4', numerator: 'Hồ sơ đã đồng bộ có ngày tiếp nhận trong kỳ', denominator: 'Giá trị lớn hơn giữa hồ sơ tiếp nhận trên BCQG và DVCQG' },
        ] },
    { id: 'dvc-progress-tree', name: 'Tiến độ giải quyết', maximum: 20, items: [
            { id: '2.1', numerator: 'Hồ sơ đã và đang xử lý đúng hạn hoặc trong hạn', denominator: 'Hồ sơ tiếp nhận, xử lý trong kỳ', caution: 'Tài liệu xác định tỷ lệ nhưng không ghi phép quy đổi điểm/điểm tối đa riêng. Phép nhân tỷ lệ × điểm tối đa đang có là cách đối chiếu trước đây, không phải phân bổ điểm được xác nhận bởi tài liệu này.' },
            { id: '2.2', numerator: 'Tổng thời gian giải quyết các hồ sơ hoàn thành', denominator: 'Tổng số hồ sơ TTHC hoàn thành', multiplier: '', caution: 'Trường avgProcessingDays hiện có được hiển thị theo ngày; không thay thế được toàn bộ chỉ tiêu đa đơn vị này.' },
        ] },
    { id: 'provide-online-tree', name: 'Dịch vụ công trực tuyến', maximum: 12, items: [
            { id: '3.1', numerator: 'TTHC có DVCTT một phần hoặc toàn trình', denominator: 'TTHC thuộc thẩm quyền giải quyết', target: 80 },
            { id: '3.2', numerator: 'DVC có hồ sơ tiếp nhận trực tuyến của TTHC', denominator: 'Số DVC của TTHC', caution: 'Phần cũ ghi ẩn khi chọn TTHC, phần Update lại mô tả theo TTHC; cần xác nhận phạm vi. Tài liệu không nêu ngưỡng 100% hoặc điểm tối đa 4 như cấu hình suy luận trước đây.' },
            { id: '3.3', numerator: 'Hồ sơ trực tuyến đáp ứng điều kiện kết quả điện tử', denominator: 'Tổng hồ sơ tiếp nhận trong kỳ', multiplier: '× hệ số đồng bộ × 100%', target: 50, caution: 'Không đủ căn cứ để dùng channelOnlineSum đơn độc khi chưa biết đã lọc kết quả điện tử và đã áp dụng hệ số đồng bộ hay chưa.' },
        ] },
    { id: 'formality-online-payment-tree', name: 'Thanh toán trực tuyến', maximum: 10, items: [
            { id: '3.5', numerator: 'TTHC có hồ sơ đồng bộ phí, lệ phí khác 0/null', denominator: 'TTHC có thông tin phí, lệ phí khác 0/null trong CSDL', target: 80, caution: 'Tài liệu có dòng “Bỏ thống kê” rồi tiếp tục bổ sung công thức; chưa rõ phần nào bị bỏ. Chưa tự gán trường API hoặc điểm tối đa riêng.' },
            { id: '3.6', numerator: 'Hồ sơ thanh toán trực tuyến trên DVCQG hoặc cổng bộ/ngành/địa phương', denominator: 'Hồ sơ thuộc TTHC có phí, lệ phí − hồ sơ có toàn bộ phí đồng bộ bằng 0', caution: 'Công thức đầu dùng số hồ sơ làm mẫu số, nhưng đoạn tình huống lại dùng số TTHC; đây là mâu thuẫn đơn vị cần xác nhận. Chưa tự tính điểm từ tham số hiện có.' },
        ] },
    { id: 'dossier-digitized', name: 'Số hóa hồ sơ', maximum: 22, items: [
            { id: '4.1', numerator: 'Hồ sơ có đường dẫn tệp kết quả điện tử hợp lệ', denominator: 'Hồ sơ thuộc TTHC yêu cầu trả kết quả bằng văn bản, giấy tờ' },
            { id: '4.2', numerator: 'Hồ sơ được số hóa và có kết quả điện tử khi TTHC yêu cầu', denominator: 'Hồ sơ TTHC thuộc thẩm quyền giải quyết', target: 80 },
            { id: '4.3', numerator: 'Hồ sơ có ít nhất một thành phần sử dụng lại dữ liệu số hóa', denominator: 'Hồ sơ có ngày tiếp nhận trong kỳ', target: 80 },
            { id: '4.4', numerator: 'Hồ sơ có thành phần lấy từ kho cá nhân hoặc kết quả điện tử đồng bộ lên danh mục', denominator: 'Hồ sơ có ngày tiếp nhận trong kỳ', caution: 'Tài liệu chưa nêu điểm tối đa hoặc cách quy đổi điểm riêng.' },
            { id: '4.5a', numerator: 'TTHC có kết nối, chia sẻ dữ liệu dân cư', denominator: 'TTHC có đối tượng thực hiện là người dân' },
            { id: '4.5b', numerator: 'Hồ sơ sử dụng thông tin, dữ liệu CSDL dân cư', denominator: 'Tổng hồ sơ TTHC', caution: 'Hai tỷ lệ trong mục 4.5 có mẫu số khác nhau, không gộp thành một tỷ lệ.' },
        ] },
    { id: 'handling-satisfaction', name: 'Mức độ hài lòng', maximum: 18, items: [
            { id: '5.1', numerator: 'PAKN đã tiếp nhận thuộc phân loại đang xét', denominator: 'Tổng PAKN trong kỳ theo đơn vị' },
            { id: '5.2', numerator: 'PAKN đã xử lý đúng hạn và đang xử lý trong hạn', denominator: 'PAKN tiếp nhận, xử lý trong kỳ', caution: 'Dòng tỷ lệ trong tài liệu bị lỗi văn bản; tử số ở đây là diễn giải từ các quy tắc bên dưới, cần xác nhận trước khi tính tự động.' },
            { id: '5.3', numerator: 'Tổng PAKN − PAKN không hài lòng, phản ánh tiếp hoặc quá hạn', denominator: 'Tổng PAKN tiếp nhận lần đầu trong kỳ', caution: 'Tài liệu dẫn “chỉ tiêu 5c” không khớp số mục hiện tại; cần xác nhận tham chiếu. Không cộng trùng các PAKN có nhiều dấu hiệu.' },
            { id: '5.4', numerator: '100% − (tỷ lệ hồ sơ quá hạn + tỷ lệ hồ sơ có PAKN hoặc dislike)', denominator: '', multiplier: '', target: 90 },
        ] },
];
// DOCX controls names, business rules, notes and data sources. Point ceilings
// remain independently sourced from captured API/METRICS, never inferred here.
export const formulaGroups = formulaDefinitions.map(group => ({
    ...group, items: group.items.map(formula => {
        const document = formulaDocument.records.find(row => row.id === formula.id.replace(/[ab]$/, ''));
        if (!document)
            throw new Error(`Missing formula document row: ${formula.id}`);
        let title = document.title;
        if (formula.id === '4.5a')
            title = document.business.find(line => line.startsWith('Tỷ lệ TTHC triển khai')).split(' = ')[0];
        if (formula.id === '4.5b')
            title = document.business.find(line => line.startsWith('Tỷ lệ hồ sơ TTHC sử dụng')).split(' = ')[0];
        return { ...formula, document, title, rules: document.business };
    })
}));
const esc = (v) => v.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function referenceNotice(id) {
    const group = formulaGroups.find(g => g.id === id);
    return `<button type="button" class="formula-inline formula-link" data-formula-group="${id}">∑ Công thức và điều kiện nghiệp vụ · ${esc(group.name)} <span aria-hidden="true">→</span></button>`;
}
function sourceParagraphs(lines) {
    if (!lines.length || lines.every(line => !line.trim() || /^Chưa có thông tin/.test(line)))
        return '<p class="formula-missing">Chưa có thông tin</p>';
    return lines.filter(line => line.trim()).map(line => {
        if (/Update/i.test(line))
            return `<p class="formula-source-update">${esc(line.replace(/^=+|=+$/g, '').trim())}</p>`;
        const heading = /^(TH\d:|- TH\d:|- (Trả kết quả|Hiển thị kết quả|Tình huống sử dụng)|Cách tính:|Trong đó:|Tử số:|Mẫu số:|Danh sách trạng thái)/.test(line);
        const bullet = /^[-+]|^\([123]\)|^[a-gđ]\)/.test(line);
        return `<p class="${heading ? 'formula-business-heading' : bullet ? 'formula-business-item' : 'formula-business-paragraph'}">${esc(line)}</p>`;
    }).join('');
}
function businessContent(f) {
    const business = f.document.business;
    // 4.5 contains two independently scored ratios. Keep each scope with its own
    // card; the account/data flags in the first half also define the second ratio.
    const second = business.findIndex(line => line.startsWith('Tỷ lệ hồ sơ TTHC sử dụng'));
    if (f.id === '4.5a')
        return business.slice(0, second);
    if (f.id === '4.5b')
        return [...business.slice(second), ...business.filter(line => line.includes('TaiKhoanDuocXacThucVoiVNeID') || line.includes('“taikhoanduocxacthucvoiVNeID”'))];
    return business;
}
function additionalEquations(f) {
    const fraction = (label, numerator, denominator) => `<div class="formula-equation"><span>${esc(label)} =</span><span class="formula-fraction"><span>${esc(numerator)}</span><span>${esc(denominator)}</span></span><span>× 100%</span></div>`;
    if (f.id === '3.1')
        return fraction('Tỷ lệ toàn trình', 'TTHC cung cấp DVCTT toàn trình', 'TTHC đủ điều kiện thực hiện DVCTT toàn trình') + fraction('Tỷ lệ một phần', 'TTHC cung cấp DVCTT một phần', 'TTHC thuộc thẩm quyền giải quyết');
    if (f.id === '3.3')
        return fraction('Tỷ lệ trực tiếp', 'Hồ sơ tiếp nhận trong kỳ có kênh 1 hoặc thiếu kênh', 'Tổng hồ sơ tiếp nhận trong kỳ') + fraction('Tỷ lệ bưu chính', 'Hồ sơ tiếp nhận trong kỳ có kênh 3', 'Tổng hồ sơ tiếp nhận trong kỳ');
    return '';
}
function accordion(kind, label, body, expanded = false) {
    const mark = kind === 'notes' ? 'warning' : kind === 'calculation' ? 'chart' : 'document';
    return `<details class="formula-accordion formula-accordion-${kind}"${expanded ? ' open' : ''}><summary><span class="formula-accordion-icon" aria-hidden="true">${icon(mark)}</span><span>${label}</span><span class="formula-chevron" aria-hidden="true">⌄</span></summary><div class="formula-accordion-body">${body}</div></details>`;
}
function components(f) {
    const terms = f.denominator ? [['Tử số', f.numerator], ['Mẫu số', f.denominator]] : [['Thành phần', f.numerator]];
    return `<dl class="formula-components">${terms.map(([label, value]) => `<div><dt>${label}:</dt> <dd>${esc(value)}</dd></div>`).join('')}</dl>`;
}
function formulaCard(group, f) {
    const maximum = formulaMaximums[group].find(row => row.formulaId === f.id)?.maximum ?? null;
    const maximumLabel = f.id === '5.1' ? 'Chỉ theo dõi · Không chấm điểm riêng' : maximumText(maximum);
    const equationLabel = f.id === '2.2' ? 'Thời gian trung bình' : f.id === '3.3' ? 'Tỷ lệ trực tuyến' : 'Tỷ lệ';
    const clarification = f.id === '2.1' ? 'Tài liệu mô tả cách xác định tỷ lệ đúng hạn; chưa nêu phép quy đổi điểm riêng. Điểm tối đa 20 được giữ theo dữ liệu đã xác định, không suy ra công thức chấm điểm từ mức điểm tối đa.' : f.id === '3.5' || f.id === '4.4' ? undefined : f.caution;
    const scoring = f.target ? `<div class="formula-score-equation" aria-label="Công thức quy đổi điểm"><span>Điểm =</span><span class="formula-score-cases"><span><i>P</i><sub>max</sub><small>nếu <i>R</i> ≥ ${f.target}%</small></span><span><span class="formula-fraction"><span><i>R</i> × <i>P</i><sub>max</sub></span><span>${f.target}%</span></span><small>nếu <i>R</i> &lt; ${f.target}%</small></span></span></div><p class="formula-symbols"><i>R</i>: tỷ lệ của chỉ tiêu; <i>P</i><sub>max</sub>: điểm tối đa riêng.${maximum === null ? ' Điểm tối đa riêng: Chưa xác định.' : ''}</p>` : '';
    const business = `${additionalEquations(f)}${scoring}<section class="formula-business"><h4>Mô tả nghiệp vụ</h4>${f.id.startsWith('4.5') ? `<p class="formula-business-heading">Mục 4.5: ${esc(f.document.title)}</p>` : ''}${f.id === '3.2' ? '<p class="formula-version-note">Biểu thức trên theo phần Update; mô tả trước cập nhật được giữ bên dưới để đối chiếu.</p>' : ''}${sourceParagraphs(businessContent(f))}</section>`;
    const notes = sourceParagraphs(f.document.notes) + (clarification ? `<div class="formula-clarification"><strong>Cần đối chiếu</strong><p>${esc(clarification)}</p></div>` : '');
    return `<article class="formula-card" data-formula-id="${f.id}"><div class="formula-card-heading"><span class="formula-code">${f.id}</span><h3>${esc(f.title)}</h3><div class="formula-card-meta"><span class="maximum-badge ${maximum === null ? 'unresolved' : ''}">Điểm tối đa: ${maximumLabel}</span>${f.target ? `<span class="badge good">Ngưỡng đạt: ${f.target}%</span>` : ''}</div></div>
 <section class="formula-math-section" aria-label="Công thức toán học">${f.id === '5.2' ? '<p class="formula-version-note">Dòng công thức trong tài liệu bị lỗi văn bản. Biểu thức dưới đây diễn giải từ quy tắc nghiệp vụ; chưa xác nhận phép quy đổi điểm.</p>' : ''}<div class="formula-equation"><span>${equationLabel} =</span>${f.denominator ? `<span class="formula-fraction"><span>${esc(f.numerator)}</span><span>${esc(f.denominator)}</span></span>` : `<strong>${esc(f.numerator)}</strong>`}<span>${esc(f.multiplier ?? '× 100%')}</span></div>${f.id === '3.3' ? '<p class="formula-symbols">Hệ số đồng bộ = tỷ lệ đồng bộ (%) / 100. Ví dụ: 80% → 0,8.</p>' : ''}</section>
 <div class="formula-accordions">${accordion('components', 'Giải thích thành phần', components(f), true)}${accordion('calculation', 'Cách tính và nghiệp vụ', business)}${accordion('sources', 'Nguồn dữ liệu', sourceParagraphs(f.document.dataSources))}${accordion('notes', 'Lưu ý khi đánh giá', notes)}</div></article>`;
}
export function displayedFormulas(group) {
    // Exclude the classification-only PAKN row; unknown point allocations remain visible.
    return group.items.filter(item => item.id !== '5.1');
}
export function renderFormulaReference(selected = 'transparency') {
    return `<section class="formula-page"><header class="bento-heading"><h1>Công thức tính Bộ chỉ số 766</h1><p>${formulaSource.version}</p></header>
 <nav class="formula-index" aria-label="Danh mục nhóm công thức">${formulaGroups.map(g => `<button type="button" data-formula-group="${g.id}" aria-label="${g.name}, tối đa ${g.maximum} điểm" aria-pressed="${g.id === selected}" style="--formula-color:${groupColors[g.id]}">${groupIcon(g.id)}<span class="formula-group-name">${g.name}</span><strong class="formula-group-maximum" aria-hidden="true">${g.maximum}</strong></button>`).join('')}</nav>
 <details class="formula-guide"><summary>Sổ tay nghiệp vụ · Nguyên tắc đọc kết quả</summary><div><p>Nguồn: ${esc(formulaSource.name)} và bảng METRICS trong Công thức 766.xlsx do quản trị viên cung cấp.</p><ul><li><strong>Tỷ lệ:</strong> tử số / mẫu số × 100%; riêng 3.3 nhân thêm hệ số đồng bộ.</li><li><strong>Quy đổi điểm:</strong> chỉ áp dụng ngưỡng và điểm tối đa khi đã xác định. Mức điểm tối đa không đồng nghĩa công thức quy đổi đã được xác nhận.</li><li><strong>Thiếu dữ liệu:</strong> không phải số 0. Mức điểm chưa rõ ghi “Chưa xác định”; điểm nguồn được giữ nguyên.</li></ul></div></details>
 ${formulaGroups.filter(g => g.id === selected).map(g => `<section class="formula-group" id="formula-${g.id}" style="--formula-color:${groupColors[g.id]}"><header><span class="bento-icon">${groupIcon(g.id)}</span><h2>${g.name}</h2></header>${displayedFormulas(g).map(f => formulaCard(g.id, f)).join('')}</section>`).join('')}</section>`;
}
//# sourceMappingURL=formula-reference.js.map