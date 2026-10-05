/** Compact loading state; replaced by real content or the existing error view. */
export function pageLoader(): string {
  return '<div class="page-loader" role="status" aria-live="polite"><div class="page-loader-mark" aria-hidden="true"><span><img class="cchc-logo" src="/assets/logo-cchc.png" alt="" width="52" height="52"></span></div><p class="page-loader-label">Đang tải dữ liệu…</p></div>';
}
