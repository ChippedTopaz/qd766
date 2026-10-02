import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildUnitView } from "../dist/analytics.js";
import { buildAnalysisCsv, encodeCsv } from "../dist/csv-export.js";

const encoded = encodeCsv([[0, null, -1.25, '=HYPERLINK("unsafe")', 'Tên; "cơ quan"\nDòng 2']]);
assert.ok(encoded.startsWith('\uFEFF"0";"";"-1,25";'));
assert.ok(encoded.includes('"\'=HYPERLINK(""unsafe"")"'));
assert.ok(encoded.includes('"Tên; ""cơ quan""\nDòng 2"'));

const data = JSON.parse(readFileSync(new URL("../data/snapshots.json", import.meta.url)));
const [key, source] = Object.entries(data.snapshots).find(([key]) => key.endsWith(":all"));
const period = data.periods.find(item => key.startsWith(`${item.id}:`));
const snapshot = structuredClone(source);
const view = buildUnitView(data, period.id, "all", data.province.id);
view.groups[0].score = {kind: "ZERO_VALUE", value: 0};
view.groups[1].score = {kind: "NO_DATA_NULL", value: null};
snapshot.delivery = {capturedAt: "2026-10-02T07:00:00+07:00", detailsCapturedAt: "2026-09-28T09:00:00+07:00", stale: true};
const scores = buildAnalysisCsv(view, snapshot, period, data.province.name, "Tất cả TTHC", "scores");
assert.ok(scores.includes('"Đã quá hạn cập nhật"'));
assert.ok(scores.includes(`"${view.groups[0].label}";"0";`));
assert.ok(scores.includes(`"${view.groups[1].label}";"";`));
assert.ok(scores.includes('"Tổng điểm";'));

const childId = source.datasets[0].children[0].departmentId;
const childView = buildUnitView(data, period.id, "all", childId);
const details = buildAnalysisCsv(childView, snapshot, period, data.province.name, "Tất cả TTHC", "details");
assert.ok(details.includes(`"${childView.name.replaceAll('"', '""')}"`));
assert.ok(details.includes('"Tham số gốc; chưa quy đổi thành điểm"') || details.includes('"Số liệu nguồn; ô trống không đồng nghĩa bằng 0"'));
console.log("CSV_EXPORT_OK");
