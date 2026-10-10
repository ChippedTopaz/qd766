import { loginView } from './login-view.js';
export function registrationBirthDate(value, today = new Date()) {
    const match = /^([0-9]{2})\/([0-9]{2})\/([0-9]{4})$/.exec(value.trim());
    if (!match)
        throw new Error('Ngày sinh phải có định dạng dd/mm/yyyy.');
    const day = Number(match[1]), month = Number(match[2]), year = Number(match[3]);
    const date = new Date(0);
    date.setFullYear(year, month - 1, day);
    date.setHours(0, 0, 0, 0);
    if (year < 1 || date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day)
        throw new Error('Ngày sinh không hợp lệ.');
    const current = new Date(today);
    current.setHours(0, 0, 0, 0);
    if (date > current)
        throw new Error('Ngày sinh không được ở tương lai.');
    return `${match[3]}-${match[2]}-${match[1]}`;
}
export function registrationFieldError(field, value) {
    const text = typeof value === 'string' ? value.trim() : '';
    switch (field) {
        case 'fullName': return !text ? 'Vui lòng nhập họ và tên.' : text.length < 2 ? 'Họ và tên phải có ít nhất 2 ký tự.' : text.length > 160 ? 'Họ và tên không được quá 160 ký tự.' : /[\x00-\x1f]/.test(text) ? 'Họ và tên không hợp lệ.' : '';
        case 'birthDate':
            if (!text)
                return 'Vui lòng nhập hoặc chọn ngày sinh.';
            try {
                registrationBirthDate(text);
                return '';
            }
            catch (error) {
                return error instanceof Error ? error.message : 'Ngày sinh không hợp lệ.';
            }
        case 'gender': return ['male', 'female'].includes(text) ? '' : 'Vui lòng chọn giới tính.';
        case 'workplace': return text.length > 240 ? 'Đơn vị công tác không được quá 240 ký tự.' : text && text.length < 2 ? 'Đơn vị công tác phải có ít nhất 2 ký tự.' : /[\x00-\x1f]/.test(text) ? 'Đơn vị công tác không hợp lệ.' : '';
        case 'province': return text ? '' : 'Vui lòng chọn tỉnh/thành phố.';
        case 'unit': return text ? '' : 'Vui lòng chọn cơ quan, đơn vị.';
        case 'declarationAccepted': return value === true ? '' : 'Vui lòng tích xác nhận cam đoan thông tin đăng ký.';
        default: return 'Thông tin đăng ký không hợp lệ.';
    }
}
export async function mountTrialRegistration(root, local) {
    const response = await fetch('/api/v1/auth/registration', { cache: 'no-store' });
    if (!response.ok)
        return false;
    let profile = await response.json();
    if (profile.state === 'approved')
        return false;
    root.innerHTML = loginView({ pending: true, name: profile.name, local, googleEnabled: true });
    const form = root.querySelector('.login-form');
    form.classList.add('registration-panel');
    const logout = async () => {
        const button = form.querySelector('[data-logout]');
        if (button.disabled)
            return;
        button.disabled = true;
        try {
            const reply = await fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-QD766-CSRF': profile.csrfToken } });
            if (!reply.ok && reply.status !== 303)
                throw new Error('Chưa thể chuyển sang đăng nhập. Vui lòng thử lại.');
            location.assign('/api/v1/auth/google/start');
        }
        catch (error) {
            form.querySelector('[data-message]').textContent = error instanceof Error ? error.message : 'Không thể đăng nhập.';
            button.disabled = false;
        }
    };
    if (profile.state === 'draft') {
        form.innerHTML = '<h2 id="login-title">Đăng ký dùng thử</h2><p class="login-description">Chọn tỉnh và cơ quan công tác.</p><form data-registration><label>Tỉnh/thành phố<select data-province required></select></label><label>Cơ quan, đơn vị<select data-unit required></select></label><p class="login-foot">Phạm vi sử dụng: cơ quan được phê duyệt.</p><p data-message role="status"></p><button type="submit" class="btn primary">Gửi đăng ký</button></form><button type="button" class="text-button" data-logout>Đăng nhập nếu đã là thành viên</button>';
        const isPublic = profile.publicRegistration === true;
        if (isPublic) {
            form.querySelector('h2').textContent = 'Đăng ký tài khoản';
            form.querySelector('.login-description').remove();
            const fields = document.createElement('div');
            fields.className = 'registration-fields';
            fields.innerHTML = '<label>Họ và tên<input name="fullName" autocomplete="name" minlength="2" maxlength="160" required></label><div class="registration-row"><label>Ngày sinh<span class="registration-calendar"><input name="birthDate" type="text" inputmode="numeric" autocomplete="bday" placeholder="dd/mm/yyyy" pattern="[0-9]{2}/[0-9]{2}/[0-9]{4}" maxlength="10" required><button type="button" data-calendar aria-label="Mở lịch chọn ngày sinh" title="Chọn ngày sinh">▦</button><input type="date" data-date-picker aria-label="Lịch chọn ngày sinh" tabindex="-1"></span></label><label>Giới tính<select name="gender" required><option value="">Chọn giới tính</option><option value="male">Nam</option><option value="female">Nữ</option></select></label></div><label>Đơn vị công tác<input name="workplace" maxlength="240" minlength="2" autocomplete="organization"></label>';
            const birth = fields.querySelector('[name=birthDate]');
            const picker = fields.querySelector('[data-date-picker]');
            const today = new Date();
            picker.max = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
            picker.addEventListener('change', () => { if (picker.value) {
                const [year, month, day] = picker.value.split('-');
                birth.value = `${day}/${month}/${year}`;
                birth.dispatchEvent(new Event('input', { bubbles: true }));
            } });
            fields.querySelector('[data-calendar]').addEventListener('click', () => {
                try {
                    picker.value = registrationBirthDate(birth.value);
                }
                catch {
                    picker.value = '';
                }
                if (typeof picker.showPicker === 'function')
                    picker.showPicker();
                else {
                    picker.focus();
                    picker.click();
                }
            });
            form.querySelector('form').prepend(fields);
            const emailLabel = document.createElement('label');
            emailLabel.textContent = 'Email đăng ký';
            const email = document.createElement('input');
            email.type = 'email';
            email.readOnly = true;
            email.value = profile.email;
            email.setAttribute('aria-label', 'Email đăng ký');
            email.title = 'Email đã được xác minh bằng Google';
            emailLabel.append(email);
            fields.prepend(emailLabel);
            form.querySelector('.login-foot').remove();
            fields.querySelector('[name=workplace]').required = false;
            const declaration = document.createElement('label');
            declaration.className = 'registration-declaration';
            declaration.innerHTML = '<input type="checkbox" name="declarationAccepted" required><span>Tôi cam đoan thông tin đăng ký tài khoản là chính xác và chịu trách nhiệm về thông tin đã đăng ký.</span>';
            form.querySelector('[data-message]').before(declaration);
            form.querySelector('[type=submit]').textContent = 'Đăng ký';
        }
        const directoryResponse = await fetch('/api/v1/auth/registration/directory', { cache: 'no-store' });
        if (!directoryResponse.ok)
            throw new Error('Chưa tải được danh sách tỉnh/cơ quan. Vui lòng thử lại.');
        const directory = await directoryResponse.json();
        const province = form.querySelector('[data-province]');
        const unit = form.querySelector('[data-unit]');
        const submit = form.querySelector('[type=submit]');
        const message = form.querySelector('[data-message]');
        const tier = form.querySelector('[name=accessTier]');
        for (const item of directory.provinces) {
            const option = new Option(item.name, item.id);
            province.add(option);
        }
        const units = new TomSelect(unit, { placeholder: 'Tìm cơ quan, đơn vị…', maxItems: 1, create: false });
        let loading = 0;
        const loadUnits = async () => {
            const version = ++loading;
            submit.disabled = true;
            units.disable();
            units.clear();
            units.clearOptions();
            message.textContent = '';
            unit.required = tier?.value !== 'province';
            unit.closest('label').hidden = tier?.value === 'province';
            if (tier?.value === 'province') {
                submit.disabled = false;
                return;
            }
            try {
                const reply = await fetch(`/api/v1/auth/registration/directory?provinceId=${encodeURIComponent(province.value)}`, { cache: 'no-store' });
                if (!reply.ok)
                    throw new Error('Chưa tải được danh sách cơ quan.');
                const data = await reply.json();
                if (version !== loading)
                    return;
                units.addOptions(data.units.map(item => ({ value: item.id, text: item.name })));
                units.enable();
                if (!data.units.length)
                    message.textContent = 'Tỉnh này chưa có danh sách cơ quan.';
            }
            catch (error) {
                if (version === loading)
                    message.textContent = error instanceof Error ? error.message : 'Không thể tải danh sách.';
            }
            finally {
                if (version === loading)
                    submit.disabled = false;
            }
        };
        const provinces = new TomSelect(province, { placeholder: 'Tìm tỉnh/thành phố…', maxItems: 1, create: false, onChange: () => void loadUnits() });
        tier?.addEventListener('change', () => void loadUnits());
        await loadUnits();
        const registrationForm = form.querySelector('form');
        registrationForm.noValidate = true;
        const controls = [];
        for (const field of isPublic ? ['fullName', 'birthDate', 'gender', 'workplace', 'declarationAccepted'] : []) {
            controls.push({ field, control: form.querySelector(`[name=${field}]`) });
        }
        controls.push({ field: 'province', control: province }, { field: 'unit', control: unit });
        const validateControl = ({ field, control }) => {
            const error = registrationFieldError(field, control instanceof HTMLInputElement && control.type === 'checkbox' ? control.checked : control.value);
            const label = control.closest('label');
            let note = label.querySelector('[data-field-error]');
            if (!note) {
                note = document.createElement('span');
                note.dataset.fieldError = field;
                note.id = `registration-error-${field}`;
                note.className = 'registration-field-error';
                label.append(note);
                control.setAttribute('aria-describedby', note.id);
            }
            note.textContent = error;
            note.hidden = !error;
            control.setAttribute('aria-invalid', String(Boolean(error)));
            return error;
        };
        for (const item of controls) {
            for (const event of ['input', 'change'])
                item.control.addEventListener(event, () => { if (item.control.hasAttribute('aria-invalid'))
                    validateControl(item); });
        }
        registrationForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (submit.disabled)
                return;
            message.textContent = '';
            let firstInvalid;
            for (const item of controls) {
                if (validateControl(item) && !firstInvalid)
                    firstInvalid = item;
            }
            if (firstInvalid) {
                if (firstInvalid.field === 'province')
                    provinces.focus();
                else if (firstInvalid.field === 'unit')
                    units.focus();
                else
                    firstInvalid.control.focus();
                return;
            }
            submit.disabled = true;
            try {
                const payload = isPublic ? { provinceId: province.value, unitId: unit.value, accessTier: 'agency',
                    fullName: form.querySelector('[name=fullName]').value, birthDate: registrationBirthDate(form.querySelector('[name=birthDate]').value),
                    gender: form.querySelector('[name=gender]').value, workplace: form.querySelector('[name=workplace]').value,
                    declarationAccepted: form.querySelector('[name=declarationAccepted]').checked }
                    : { provinceId: province.value, unitId: unit.value };
                const reply = await fetch(isPublic ? '/api/v1/auth/registration/public' : '/api/v1/auth/registration', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': profile.csrfToken }, body: JSON.stringify(payload) });
                const body = await reply.json();
                if (!reply.ok)
                    throw new Error(typeof body.detail === 'string' ? body.detail : 'Không thể gửi đăng ký.');
                provinces.destroy();
                units.destroy();
                profile.state = 'pending';
                waiting();
            }
            catch (error) {
                message.textContent = error instanceof Error ? error.message : 'Không thể gửi đăng ký.';
                submit.disabled = false;
            }
        });
        form.querySelector('[data-logout]').addEventListener('click', () => void logout());
    }
    else
        waiting();
    function waiting() {
        form.innerHTML = '<h2 id="login-title" data-heading></h2><p class="login-description" data-description></p><p data-message role="status"></p><button class="btn primary" data-check>Kiểm tra trạng thái</button><a class="login-google" href="/" data-enter hidden>Vào hệ thống</a><button type="button" class="text-button" data-logout>Đăng nhập nếu đã là thành viên</button>';
        const display = () => {
            form.querySelector('[data-heading]').textContent = profile.state === 'approved' ? 'Đăng ký đã được duyệt' : profile.state === 'rejected' ? 'Đăng ký chưa được phê duyệt' : 'Đang chờ phê duyệt';
            form.querySelector('[data-description]').textContent = profile.state === 'approved' ? 'Tài khoản đã sẵn sàng sử dụng.' : profile.state === 'rejected' ? 'Vui lòng liên hệ quản trị viên.' : 'Đăng ký thành công. Hồ sơ của bạn đã được gửi đến quản trị viên để xét duyệt. Sau khi được duyệt, bạn có thể đăng nhập bằng tài khoản Google đã đăng ký.';
            form.querySelector('[data-enter]').hidden = profile.state !== 'approved';
            form.querySelector('[data-check]').hidden = profile.state === 'approved';
        };
        const check = async () => {
            const button = form.querySelector('[data-check]');
            button.disabled = true;
            try {
                const reply = await fetch('/api/v1/auth/registration', { cache: 'no-store' });
                if (!reply.ok)
                    throw new Error('Phiên đã hết hạn. Vui lòng đăng nhập lại.');
                profile = await reply.json();
                display();
                form.querySelector('[data-message]').textContent = '';
            }
            catch (error) {
                form.querySelector('[data-message]').textContent = error instanceof Error ? error.message : 'Chưa kiểm tra được trạng thái.';
            }
            finally {
                button.disabled = false;
            }
        };
        form.querySelector('[data-check]').addEventListener('click', () => void check());
        form.querySelector('[data-logout]').addEventListener('click', () => void logout());
        display();
        const poll = () => window.setTimeout(async () => { if (!form.isConnected || profile.state !== 'pending')
            return; if (!document.hidden)
            await check(); poll(); }, 15000);
        poll();
    }
    return true;
}
//# sourceMappingURL=trial-registration.js.map