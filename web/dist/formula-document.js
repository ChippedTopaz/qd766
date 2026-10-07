export const formulaDocument = {
    "name": "Mô tả công thức tính chỉ số 766.docx",
    "sha256": "41A27E55E251C616408D310EE7467CC831D373ED95B108FD65D5832A337087AF",
    "records": [
        {
            "id": "1.1",
            "title": "Tỷ lệ thủ tục hành chính công bố đúng hạn",
            "group": "1. Nhóm chỉ số về công khai, minh bạch",
            "business": [
                "= Số thủ tục hành chính công bố đúng hạn/Tổng số thủ tục hành chính đã công bố trong kỳ * 100%",
                "TH1: Bộ Ngành",
                "Tổng số TTHC công bố đúng hạn là tổng số TTHC thỏa mãn:",
                "-Kể từ thời điểm công bố QĐCB, Ngày quyết định của QĐCB <= \"Ngày hiệu lực\" mới nhất của văn bản cơ sở pháp lý của TTHC - 20 ngày làm việc",
                "Tổng số TTHC công bố trong kỳ: là tổng số TTHC đang công khai loại thêm mới, sửa đổi, bãi bỏ trong các QĐCB có \"Ngày quyết định\" trong kỳ. Nếu 1 TT xuất hiện trong nhiều QĐCB thì chỉ tính 1 TTHC.",
                "TH2: Tỉnh/TP",
                "Tổng số TTHC công bố đúng hạn là tổng số TTHC thỏa mãn:",
                "- Kể từ thời điểm công bố QĐCB đặc thù, Ngày quyết định của QĐCB <= \"Ngày hiệu lực\" mới nhất của văn bản cơ sở pháp lý của TTHC - 5 ngày làm việc",
                "Tổng số TTHC công bố trong kỳ: số TTHC đang công khai trong QĐCB loại thêm mới/ sửa đổi, bổ sung /bãi bỏ có “Ngày quyết định” trong kỳ",
                "Trong 1 kỳ, nếu 1 TTHC xuất hiện trong nhiều QĐCB thì chỉ tính 1 TTHC.",
                "Chỉ tiêu này chỉ xét các TTHC được công khai trong kỳ. Trường hợp trong cùng 1 kỳ, TTHC sửa đổi nhiều lần trong nhiều QĐCB: nếu có ít nhất 1 lần quá hạn thì cả kỳ quá hạn."
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC"
            ]
        },
        {
            "id": "1.2",
            "title": "Tỷ lệ thủ tục hành chính được cập nhật, công khai đúng hạn",
            "group": "1. Nhóm chỉ số về công khai, minh bạch",
            "business": [
                "= Số TTHC công khai đúng hạn trên CSDL QG về TTHC/Tổng số TTHC phải cập nhật, công khai trên CSDL QG về TTHC trong kỳ * 100%.",
                "Tử số: Số TTHC công khai đúng hạn trên CSDL QG về TTHC là tổng số TTHC thỏa mãn:",
                "- TH1: Bộ Ngành",
                "Ngày click Công khai của TTHC được công khai gần nhất trong QĐ Công bố <= 10 ngày làm việc so với \"Ngày quyết định\" của QĐ Công bố",
                "(Ngày click - 10 ngày làm việc <= ngày ký quyết định công bố)",
                "- TH2: Tỉnh/TP",
                "Ngày click Công khai của TTHC được công khai gần nhất trong QĐ Công bố <= 5 ngày làm việc so với \"Ngày quyết định\" của QĐ Công bố",
                "(Ngày click - 5 ngày làm việc <= ngày ký quyết định công bố)",
                "Mẫu số: Tổng số TTHC phải cập nhật, công khai trên CSDL QG về TTHC trong kỳ= tổng số TTHC đã công khai trong kỳ (Nếu 1 TT xuất hiện trong nhiều QĐCB thì chỉ tính 1 TTHC) + tổng số TTHC cần công khai trong kỳ",
                "Trong đó:",
                "- Tổng số TTHC cần công khai trong kỳ được tính như sau :",
                "++ Trạng thái TTHC = Đang công khai, Đang công khai sửa đổi bổ sung, Bãi bỏ",
                "++ Bộ: Ngày QĐ của QĐCB <= Ngày cuối kỳ thống kê + 10 ngày làm việc",
                "++ Tỉnh: Ngày QĐ của QĐCB <= Ngày cuối kỳ thống kê +5 ngày làm việc",
                "- Tổng số TTHC đã công khai trong kỳ thỏa mãn :",
                "++ Trạng thái TTHC = Đang công khai, Đang công khai sửa đổi bổ sung, Bãi bỏ",
                "Chỉ tiêu này không thông kê theo TTHC.",
                "Chỉ thống kê theo cấp Tỉnh, Bộ Ngành (Không tính cấp con)",
                "Chỉ tiêu này chỉ xét các TTHC được công khai thêm mới, sửa đổi, bãi bỏ trong kỳ. Trường hợp trong cùng 1 kỳ, TTHC sửa đổi nhiều lần trong nhiều QĐCB: nếu có ít nhất 1 lần quá hạn thì cả kỳ quá hạn."
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC"
            ]
        },
        {
            "id": "1.3",
            "title": "Tỷ lệ thủ tục hành chính được công khai có đầy đủ các nội dung quy định về các bộ phận tạo thành của thủ tục hành chính",
            "group": "1. Nhóm chỉ số về công khai, minh bạch",
            "business": [
                "= Số TTHC có đầy đủ thông tin về các bộ phận tạo thành theo quy định tại khoản 2 Điều 8 Nghị định số 63/2010/NĐ-CP ngày 08 tháng 6 năm 2010 của Chính phủ về kiểm soát thủ tục hành chính (đã được sửa đổi, bổ sung)/Tổng số thủ tục hành chính đã được cập nhật, công khai trên Cơ sở dữ liệu quốc gia về thủ tục hành chính * 100%.",
                "- Tổng số TTHC có đầy đủ thông tin về bộ phận tạo thành: là số TTHC đang công khai trong kỳ hiện tại trên Cổng có đầy đủ:",
                "a) Tên thủ tục hành chính;",
                "b) Trình tự thực hiện;",
                "c) Cách thức thực hiện;",
                "d) Thành phần, số lượng hồ sơ;",
                "đ) Thời hạn giải quyết;",
                "e) Đối tượng thực hiện thủ tục hành chính;",
                "g) Cơ quan thực hiện thủ tục hành chính",
                "Đối với các mẫu đơn, mẫu tờ khai, mẫu kết quả....thì không kiểm tra được do không kiểm tra được điều kiện TTHC nào bắt buộc phải có",
                "-Tổng số TTHC đã được cập nhật, công khai trên CSDL QG về TTHC: số TTHC \"công khai\" trên Cổng QG (TTHC có trạng thái \"Đã công khai, Đã công khai sửa đổi bổ sung\")",
                "Chỉ tiêu này không thống kê theo TTHC và theo đơn vị cấp dưới của Tỉnh, Bộ (khi chọn TTHC và đơn vị cấp dưới tỉnh bộ thì ẩn biểu đồ)",
                "Chỉ tiêu không tính theo thời gian. (tính đến thời điểm hiện tại)"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC"
            ]
        },
        {
            "id": "1.4",
            "title": "Tỷ lệ hồ sơ đồng bộ lên Cổng Dịch vụ công quốc gia",
            "group": "1. Nhóm chỉ số về công khai, minh bạch",
            "business": [
                "Tỷ lệ hồ sơ đã đồng bộ = Số lượng hồ sơ đã đồng bộ có “Ngày tiếp nhận” trong kỳ báo cáo/ Tổng số hồ sơ được tính toán trong kỳ * 100%.",
                "Trong đó:",
                "- Tổng số hồ sơ được tính toán trong kỳ: So sánh giữa tổng số hồ sơ tiếp nhận trong kỳ với tổng số hồ sơ tiếp nhận trong kỳ ở Hệ thống báo cáo quốc gia và trong báo cáo thống kê tình hình xử lý hồ sơ được đồng bộ lên Cổng Dịch vụ công quốc gia. Trong trường hợp tổng số hồ sơ tiếp nhận trong kỳ ở Hệ thống báo cáo quốc gia lớn hơn tổng số hồ sơ tiếp nhận trong kỳ trên Cổng Dịch vụ công quốc gia thì lấy tổng số hồ sơ tiếp nhận trong kỳ ở Hệ thống báo cáo quốc gia.",
                "Nếu hệ thống BCQG và DVCQG không có số lượng hồ sơ cần đồng bộ (mẫu số =0 hoặc null) thì tính toán theo cách sau:",
                "Mẫu số (kỳ báo cáo tháng) = Tổng số lượng hồ sơ của báo cáo năm trước liền kề (báo cáo năm) trong hệ thống BCQG / 12 tháng",
                "Mẫu số (kỳ báo cáo quý) = Tổng số lượng hồ sơ năm trước liền kề trong hệ thống BCQG / 4",
                "Mẫu số (kỳ báo cáo năm)= Tổng số lượng hồ sơ của năm trước liền kề.",
                "Nếu năm trước liền kề không có số liệu, tỷ lệ hồ sơ đồng bộ = 0.",
                "(Hồ sơ đã đồng bộ - tính cả đồng bộ 1 chiều, bao gồm cả 1 chiều từ DVC đến BNĐP)"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "2.1",
            "title": "Tỷ lệ hồ sơ xử lý trước hạn, đúng hạn",
            "group": "2. Nhóm chỉ số về tiến độ, kết quả giải quyết",
            "business": [
                "Tỷ lệ hồ sơ xử lý đúng hạn= Số lượng hồ sơ đã và đang xử lý đúng hạn hoặc trong hạn trong kỳ/ Tổng số hồ sơ được tiếp nhận, xử lý trong kỳ",
                "Hồ sơ được tiếp nhận, xử lý trong kỳ được tính đúng hạn, trong hạn khi: Thời gian kết thúc xử lý (trường NgayKetThucXuLy) <= Ngày hẹn trả (trường NgayHenTra).",
                "- Thời gian kết thúc xử lý là thời điểm tương ứng với trạng thái kết thúc xử lý hồ sơ (Từ chối, Dừng xử lý, Đã xử lý xong, Đã trả kết quả, Công dân yêu cầu rút hồ sơ -  chỉ tính các hồ sơ đã được tiếp nhận) trong tiến trình xử lý. Nếu tiến trình xử lý có đồng thời trạng thái Đã xử lý xong, Đã trả kết quả thì hệ thống ưu tiên lấy thời gian Đã xử lý xong.",
                "Nếu hồ sơ đang yêu cầu bổ sung, công dân chưa quay lại bổ sung hồ sơ thì lấy ngày cán bộ yêu cầu bổ sung hồ sơ là Thời gian kết thúc xử lý. (Nếu tiến trình chỉ có trạng thái “Yêu cầu bổ sung hồ sơ” mà không có trạng thái “Đã xử lý xong” hoặc “Đã trả kết quả” thì thời hạn hoàn thành xử lý là thời điểm theo trạng thái “Yêu cầu bổ sung hồ sơ”, trừ trường hợp “Yêu cầu bổ sung hồ sơ” hơn 01 lần thì tính quá hạn.)",
                "- Ngày hẹn trả: Ngày hẹn trả trong thông tin hồ sơ đồng bộ.",
                "Nếu không có ngày hẹn trả thì được tính theo công thức: Thời gian kết thúc xử lý hồ sơ -  Thời gian bắt đầu xử lý - Thời gian bổ sung hồ sơ <= Thời hạn tối đa giải quyết TTHC",
                "Trong đó, thời gian bắt đầu xử lý: Ngày tiếp nhận hồ sơ.",
                "Chưa có trạng thái hoàn thành → lấy ngày cuối kỳ báo cáo là ngày kết thúc xử lý.",
                "Thời gian kết thúc xử lý: thời điểm đạt trạng thái \"Đã xử lý xong\" > \"Đã trả kết quả\" > \"Dừng xử lý/Từ chối\". Nếu chỉ có \"Yêu cầu bổ sung\" (1 lần) → lấy thời điểm đó.",
                "-  Nếu hồ sơ kết thúc xử lý có  \"Yêu cầu bổ sung\" -> Thực hiện trừ thời gian bổ sung hồ sơ của công dân để tính lại thời gian kết thúc xử lý hồ sơ:",
                "( Thời gian kết thúc xử lý hồ sơ = Thời gian kết thúc xử lý - Thời gian bổ sung hồ sơ. Thời gian bổ sung hồ sơ = Thời điểm \"hoàn thành bổ sung hồ sơ\" - Thời điểm \"Yêu cầu bổ sung\")",
                "Đúng hạn : Ngày kết thúc xử lý hồ sơ  <, =  ngày hẹn trả."
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "2.2",
            "title": "Thời gian giải quyết TTHC trung bình theo từng TTHC",
            "group": "2. Nhóm chỉ số về tiến độ, kết quả giải quyết",
            "business": [
                "Thời gian giải quyết TTHC trung bình = Tổng thời gian giải quyết của các hồ sơ TTHC/Tổng số hồ sơ TTHC.",
                "- Tổng số hồ sơ hoàn thành gồm c, ác hồ sơ thỏa mãn:",
                "+ Thuộc trạng thái: Đã xử lý xongĐã trả kết quả,",
                "+ Có Thời gian bắt đầu xử lý trong kỳ",
                "Ngày kết thúc xử lý có thể thuộc kỳ khác",
                "- Tổng thời gian giải quyết của các hồ sơ TTHC = Tổng thời gian giải quyết TTHC của tất cả hồ sơ đã hoàn thành (trường ThoiGianGiaiQuyet)",
                "(Tổng thời gian được tính tương tự chỉ tiêu 2a). Loại thời gian trung bình tính theo Giờ, Ngày, Ngày làm việc, tháng tính theo thời gian tối đa giải quyết TTHC (trường DonViTinh)",
                "Chỉ tiêu này chỉ hiển thị khi chọn 1 TTHC cụ thể.",
                "Chỉ tiêu này được tính theo đơn vị giải quyết. Nếu chọn thống kê theo tỉnh thì thống kê tất cả hồ sơ thuộc chính nó và đơn vị cấp con của nó. Trường hợp thống kê theo Bộ, thì thống kê hai loại: TTHC thuộc phạm vi giải quyết củacấp Bộ, ngành dọc và tất cả hồ sơ của nó ở tỉnh. (Công An, Quốc phòng, Tài chính (BHXH, Thuế), Hải quan......)"
            ],
            "notes": [
                "Chưa có thông tin trong sheet."
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "3.1",
            "title": "Tỷ lệ TTHC cung cấp dịch vụ công trực tuyến",
            "group": "3. Nhóm chỉ số về cung cấp dịch vụ trực tuyến",
            "business": [
                "Tỷ lệ TTHC cung cấp dịch vụ công trực tuyến =Số TTHC có DVCTT một phần, DVCTT toàn trình /Tổng số TTHC thuộc thẩm quyền giải quyết của tỉnh (bao gồm tỉnh, xã), của Bộ, ngành (bao gồm cả các TTHC ngành dọc).",
                "Trường hợp 01 TTHC được cung cấp cả DVCTT một phần và toàn trình thì tính cho mức DVCTT cao nhất.",
                "- Trả kết quả theo địa bàn hành chính:",
                "+ Cả nước: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC gốc (của các Bộ) cung cấp DVCTT tích “công khai” trên Cổng áp dụng cho các Tỉnh, xã/ Tổng số TTHC gốc của cả nước.",
                "+ Bộ: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC cung cấp DVCTT tích “công khai” trên Cổng của Bộ/Tổng số TTHC gốc thuộc thẩm quyền giải quyết của Bộ (bao gồm cả các TTHC tích ngành dọc).",
                "+ Tỉnh, Thành phố: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC của tỉnh cung cấp DVCTT công khai trên Cổng/ Tổng số TTHC của Tỉnh",
                "+ Xã, phường: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC có đơn vị áp dụng DVCTT là xã đó/ Tổng số TTHC có cấp thực hiện = cấp xã",
                "- Hiển thị kết quả TTHC cung cấp dịch vụ công trực tuyến toàn trình và một phần",
                "+ Dịch vụ công trực tuyến toàn trình: ",
                "(1) Bộ: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC cung cấp DVCTT toàn trình tích “công khai” trên Cổng/Tổng số TTHC gốc thuộc thẩm quyền giải quyết của Bộ (bao gồm cả các TTHC tích ngành dọc) đủ điều kiện thực hiện DVCTT toàn trình (căn cứ trên TTHC đã được tích đủ điều kiện thực hiện DVCTT toàn trình trên Cơ sở dữ liệu quốc gia về TTHC); ",
                "(2) Tỉnh, xã: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC của tỉnh cung cấp DVCTT toàn trình tích “công khai” trên Cổng/ Tổng số TTHC có đủ điều kiện thực hiện DVCTT toàn trình (căn cứ trên TTHC gốc đã được tích đủ điều kiện thực hiện DVCTT toàn trình trên Cơ sở dữ liệu quốc gia về TTHC) của Tỉnh (bao gồm tất cả các cấp tỉnh, xã); có cấp thực hiện là xã.",
                "+ Dịch vụ công trực tuyến một phần: ",
                "(1) Bộ: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC cung cấp DVCTT một phần tích “công khai” trên Cổng/Tổng số TTHC gốc thuộc thẩm quyền giải quyết của Bộ (bao gồm cả các TTHC tích ngành dọc); ",
                "(2) Tỉnh, xã: Biểu thị giá trị tuyệt đối và tỷ lệ % TTHC của tỉnh cung cấp DVCTT một phần tích “công khai” trên Cổng/ Tổng số TTHC của Tỉnh; có cấp thực hiện là xã.",
                "- Không thay đổi giá trị khi chọn TTHC cụ thể."
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc",
                "- Đạt từ 80% trở lên sẽ đạt điểm tối đa.",
                "- Dưới 80% tính theo công thức:",
                "Tỷ lệ % TTHC cung cấp dịch vụ công trực tuyến*Điểm tối đa/80%."
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC"
            ]
        },
        {
            "id": "3.2",
            "title": "Tỷ lệ dịch vụ công trực tuyến có phát sinh hồ sơ",
            "group": "3. Nhóm chỉ số về cung cấp dịch vụ trực tuyến",
            "business": [
                "- Tỷ lệ DVCTT có hồ sơ nộp trực tuyến không thực hiện từ Cổng: Tổng số TTHC đang áp dụng có hồ sơ “nộp trực tuyến” không được đánh dấu nộp từ Cổng DVCQG/ Tổng số TTHC có hồ sơ “nộp trực tuyến” đồng bộ trạng thái.",
                "- Mẫu số : TTHC có hồ sơ trực tuyến nộp từ Cổng DVCQG: Tổng số TTHC đang áp dụng có hồ sơ đồng bộ từ địa phương được đánh dấu nộp từ Cổng DVCQG/Tổng số TTHC có hồ sơ “nộp trực tuyến” (Kênh thực hiện = Trực tuyến) đồng bộ trạng thái.",
                "- Trả kết quả theo kỳ báo cáo: Xét các hồ sơ đồng bộ có “Ngày tiếp nhận” trong kỳ báo cáo. Nếu không có “Ngày tiếp nhận” lấy theo “Ngày nộp hồ sơ”",
                "- Trả kết quả theo TTHC: Không hiển thị biểu đồ khi chọn TTHC cụ thể (do 1 TTHC thường có 1 hoặc 2 DVCTT nên đưa ra tỷ lệ % không có ý nghĩa)",
                "- Trả kết quả theo địa bàn hành chính:",
                "+ Cả nước: Tính trên hồ sơ nộp trực tuyến được đồng bộ của tất cả các tỉnh, thành phố",
                "+ Bộ: Tính trên tất cả hồ sơ nộp trực tuyến được đồng bộ của Bộ (mã cơ quan thực hiện của Bộ và các đơn vị trực thuộc Bộ).",
                "+ Tỉnh/TP: Tính trên tất cả hồ sơ nộp trực tuyến được đồng bộ của Tỉnh và các đơn vị cấp con của nó ( có bao nhiêu cấp con thì lấy hết)",
                "+ Xã/Phường: Tính trên hồ sơ nộp trực tuyến được đồng bộ có cơ quan thực hiện là xã đó.",
                "=======Update========",
                "Tử: số dvc có hồ sơ tiếp nhận trực tuyến của tthc",
                "Mẫu: số dvc của tthc",
                "Tính theo đơn vị áp dụng  DVC (đơn vị xử lý)",
                "Trạng thai DVC: Đang công khai, chờ dừng công khai, đang kiểm thử"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC",
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "3.3",
            "title": "Tỷ lệ hồ sơ TTHC theo hình thức nộp hồ sơ",
            "group": "3. Nhóm chỉ số về cung cấp dịch vụ trực tuyến",
            "business": [
                "+ Tỷ lệ hồ sơ nộp trực tuyến: Tổng số hồ sơ tiếp nhận trực tuyến có Ngày tiếp nhận trong kỳ (1)/ Tổng số hồ sơ tiếp nhận trong kỳ * Tỷ lệ đồng bộ hồ sơ * 100%",
                "(1) NgayTiepNhan trong kỳ, KenhThucHien = 2 (Trực tuyến), và (2) cấp kết quả giải quyết điện tử đối với TTHC yêu cầu trả kết quả bằng văn bản giấy tờ (có mã kết quả + đường links kết quả). (Trường MaKetQua DuongDanTepTinKetQua)",
                "Trường hợp TTHC không yêu cầu trả kết quả bằng văn bản giấy tờ thì khi có kênh thực hiện trực tuyến “2” thì được tính hồ sơ trực tuyến.",
                "+ Tỷ lệ hồ sơ nộp trực tiếp: Tổng số hồ sơ tiếp nhận trực tiếp có Ngày tiếp nhận trong kỳ (2) và hồ sơ tiếp nhận trong kỳ mà không có dữ liệu kênh thực hiện / Tổng số hồ sơ tiếp nhận trong kỳ",
                "(2) NgayTiepNhan trong kỳ, KenhThucHien = 1 (Trực tiếp) hoặc null",
                "+ Tỷ lệ hồ sơ nộp qua đường bưu điện: Tổng số hồ sơ tiếp nhận qua bưu chính công ích có Ngày tiếp nhận trong kỳ (3)/ Tổng số hồ sơ tiếp nhận trong kỳ",
                "(3) NgayTiepNhan trong kỳ, KenhThucHien = 3 (Bưu chính công ích)"
            ],
            "notes": [
                "- Đạt từ 50% trở lên sẽ đạt điểm tối đa.",
                "- Dưới 50% tính theo công thức:",
                "Tỷ lệ hồ sơ TTHC theo hình thức nộp hồ sơ trực tuyến *Điểm tối đa/50%."
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "3.5",
            "title": "Tỷ lệ TTHC có yêu cầu nghĩa vụ tài chính được tích hợp để người dân có thể thanh toán trực tuyến trên Cổng Dịch vụ công quốc gia",
            "group": "3. Nhóm chỉ số về cung cấp dịch vụ trực tuyến",
            "business": [
                "(2) Tỷ lệ TTHC có yêu cầu nghĩa vụ tài chính được tích hợp để người dân có thể thanh toán trực tuyến trên Cổng Dịch vụ công quốc gia= X/Y* 100%",
                "X: Tổng số TTHC có hồ sơ có đồng bộ dữ liệu phí, lệ phí trên Cổng (Phí, lệ phí khác 0, null)",
                "Y: Tổng số TTHC có thông tin phí lệ phí trong CSDL thủ tục hành chính (Phí, lệ phí khác 0, null)",
                "- Chọn kỳ báo cáo: Tính X theo kỳ báo cáo. Xét hồ sơ có “Ngày tiếp nhận” trong kỳ, nếu không có ngày tiếp nhận thì lấy theo “Ngày nộp hồ sơ”. Y luôn lấy theo giá trị hiện tại trong CSDL TTHC.",
                "- Ẩn biểu đồ khi chọn TTHC cụ thể",
                "- Trả kết quả theo địa bàn hành chính: Chọn 1 địa bàn hành chính thì hiển thị các địa bàn hành chính cấp con liền kề.",
                "+ Cả nước: Xét trên các TTHC của Tỉnh (thực hiện tại cấp Tỉnh, Xã)",
                "+ Bộ: Xét trên TTHC thuộc thẩm quyền giải quyết của Bộ (bao gồm cả các TTHC tích ngành dọc).",
                "+ Tỉnh/TP: Xét trên TTHC của Tỉnh thực hiện tại cấp Tỉnh",
                "+ Xã/ Phường: Không có địa bàn cấp con",
                "Bỏ thống kê - Chưa tích hợp, cung cấp dịch vụ thanh toán trực tuyến",
                "Bổ sung theo cột Review công thức:",
                "Số liệu liên quan CSDL: Y: Tổng số TTHC có thông tin phí lệ phí trong CSDL thủ tục hành chính (Phí, lệ phí khác 0, null)"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc",
                "- Đạt từ 80% trở lên sẽ đạt điểm tối đa.",
                "- Dưới 80% tính theo công thức:",
                "Tỷ lệ TTHC có yêu cầu nghĩa vụ tài chính được tích hợp để người dân có thể thanh toán trực tuyến trên Cổng Dịch vụ công quốc gia *Điểm tối đa/80%."
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC",
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "3.6",
            "title": "Tỷ lệ hồ sơ thanh toán trực tuyến",
            "group": "3. Nhóm chỉ số về cung cấp dịch vụ trực tuyến",
            "business": [
                "Tỷ lệ hồ sơ thanh toán trực tuyến = số lượng hồ sơ đồng bộ của đơn vị được thanh toán trực tuyến ( DuocThanhToanTrucTuyen = 1: Thanh toán trực tuyến trên cổng DVCQG, 2: Thanh toán trực tuyến qua Cổng thanh toán BNĐP)có Ngày bắt đầu xử lý trong kỳ/ (Tổng số hồ sơ của các TTHC thuộc thẩm quyền giải quyết có thông tin phí, lệ phí trong Cơ sở dữ liệu quốc gia về thủ tục hành chính (Phí, lệ phí khác 0,“”, hoặc không để trống) – Tổng số hồ sơ của các TTHC này nhưng có tất cả các thông tin đồng bộ Danh sachphilephi có “Gia: 0”) * 100%.",
                "- Tình huống sử dụng:",
                "+ Thống kê theo xã: Tử số thống kê dựa trên các hồ sơ có cơ quan thực hiện là xã đó. Mẫu số: số lượng TTHC đang công khai của tỉnh có cấp thực hiện là cấp xã",
                "+ Thống kê theo Tỉnh: Tử số thống kê dựa trên các hồ sơ có cơ quan thực hiện là tỉnh đó hoặc các đơn vị con của nó. Mẫu số: số lượng TTHC đang công khai của tỉnh có cấp thực hiện là cấp tỉnh, cấp xã",
                "+ Thống kê theo Bộ: Tử số: thống kê dựa trên các hồ sơ có cơ quan thực hiện là Bộ đó hoặc các đơn vị con của nó. Mẫu số: số lượng TTHC thuộc thẩm quyền giải quyết của Bộ (bao gồm cả các TTHC tích ngành dọc)",
                "đang công khai của Bộ",
                "+ Thống kê theo TTHC: Tử số, mẫu số thống kê theo hồ sơ thuộc TTHC đã chọn",
                "+ Thống kê theo kỳ báo cáo: Thống kê tử số, mẫu số dựa trên các hồ sơ có Ngày bắt đầu xử lý trong kỳ báo cáo (Ngày bắt đầu xử lý tính theo công thức tại chỉ tiêu Tỷ lệ hồ sơ xử lý đúng hạn, trước hạn)."
            ],
            "notes": [
                "Chưa có thông tin trong sheet."
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC",
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "4.1",
            "title": "Tỷ lệ hồ sơ thủ tục hành chính có cấp kết quả giải quyết thủ tục hành chính điện tử",
            "group": "4. Nhóm chỉ số về số hóa hồ sơ",
            "business": [
                "Tỷ lệ hồ sơ thủ tục hành chính có cấp kết quả giải quyết TTHC điện tử = Tổng số hồ sơ TTHC có cấp kết quả giải quyết TTHC điện tử/Tổng số hồ sơ TTHC thuộc thẩm quyền giải quyết * 100%.",
                "Tử số = tổng số hồ sơ TTHC đồng bộ kết quả xử lý có link file kết quả giải quyết đính kèm và TTHC đó yêu cầu trả kết quả bằng văn bản, giấy tờ.",
                "Mẫu số = Tổng số hồ sơ TTHC thuộc thẩm quyền giải quyết của các TTHC có yêu cầu trả kết quả bằng văn bản, giấy tờ.",
                "Chỉ tiêu được thống kê theo thời gian và theo địa bàn hành chính:",
                "+ Bộ: tính trên hồ sơ có cơ quan thực hiện trực thuộc Bộ (bao gồm cả các cơ quan ngành dọc)",
                "+ Tỉnh, xã: Tính trên hồ sơ có cơ quan thực hiện là Tỉnh/ xã tương ứng và các đơn vị cấp dưới",
                "Chỉ tiêu được thống kê theo TTHC",
                "Tử số = Tổng số hồ sơ TTHC có hồ sơ có file kết quả đính kèm."
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "4.2",
            "title": "Tỷ lệ hồ sơ thủ tục hành chính thực hiện số hóa hồ sơ",
            "group": "4. Nhóm chỉ số về số hóa hồ sơ",
            "business": [
                "Tỷ lệ hồ sơ thủ tục hành chính thực hiện số hóa hồ sơ =",
                "[Tổng số hồ sơ thủ tục hành chính :",
                "(1) thực hiện quy trình số hóa hồ sơ, kết quả giải quyết TTHC (bao gồm hồ sơ số hóa trong tiếp nhận trực tiếp, qua bưu chính và hồ sơ trực tuyến) và",
                "(2) cấp kết quả giải quyết điện tử đối với TTHC yêu cầu trả kết quả bằng văn bản giấy tờ /Tổng số hồ sơ TTHC thuộc thẩm quyền giải quyết] * 100%.",
                "*Cách xét TTHC yêu cầu trả kết quả bằng văn bản giấy tờ theo chỉ số Tỷ lệ hồ sơ TTHC có cấp kết quả giải quyết TTHC điện tử",
                "Chỉ tiêu được thống kê theo thời gian và theo địa bàn hành chính:",
                "+ Bộ: tính trên hồ sơ có cơ quan thực hiện trực thuộc Bộ (bao gồm cả các cơ quan ngành dọc)",
                "+ Tỉnh, xã: Tính trên hồ sơ có cơ quan thực hiện là Tỉnh/xã tương ứng và các đơn vị cấp dưới",
                "Tổng số hồ sơ TTHC thực hiện số hoá :",
                "(1) số hoá hồ sơ  = Có file đính kèm trong thành phần hồ sơ",
                "(2) Có file đính kèm trong kết quả xử lý"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc",
                "- Đạt từ 80% trở lên sẽ đạt điểm tối đa.",
                "- Dưới 80% tính theo công thức:",
                "Tỷ lệ % hồ sơ TTHC thực hiện số hóa*Điểm tối đa/80%."
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "4.3",
            "title": "Tỷ lệ hồ sơ khai thác, sử dụng lại thông tin, dữ liệu số hóa",
            "group": "4. Nhóm chỉ số về số hóa hồ sơ",
            "business": [
                "Tỷ lệ khai thác, sử dụng lại thông tin, dữ liệu số hóa = Tổng số hồ sơ TTHC có sử dụng lại thông tin, dữ liệu, giấy tờ điện tử đã được số hóa/Tổng số hồ sơ TTHC thuộc thẩm quyền giải quyết * 100%.",
                "Tổng số hồ sơ TTHC có thành phần hồ sơ sử dụng lại thông tin giấy tờ điện tử đã được số hóa = Tổng số hồ sơ TTHC có ngày tiếp nhận trong kỳ của đơn vị có ít nhất 1 thành phần hồ sơ được đánh dấu tái sử dụng dữ liệu số hóa trong thành phần hồ sơ",
                "DG: Tổng số hồ sơ TTHC có thành phần hồ sơ sử dụng lại thông tin giấy tờ điện tử đã được số hóa được hiểu là DVC tromg CSDL đc đánh dấu = lấy thông tin, kiểm tra thông tin, eform",
                "Hồ sơ đồng bộ từ Bộ ngành : lấy thông tin tường: HoSoCoThanhPhanSoHoa = 1",
                "Đối với hồ sơ tạo từ Cổng : Trong TaiLieuNop trường DuocSoHoa = 1",
                "Nếu không có ngày tiếp nhận thì không tính hồ sơ.",
                "Tổng số hồ sơ TTHC thuộc thẩm quyền giải quyết = Tổng số hồ sơ có Ngày tiếp nhận trong kỳ.",
                "Chỉ tiêu được thống kê theo thời gian và theo địa bàn hành chính:",
                "+ Bộ: tính trên hồ sơ có cơ quan thực hiện trực thuộc Bộ",
                "+ Tỉnh, xã: Tính trên hồ sơ có cơ quan thực hiện là Tỉnh/ xã tương ứng và các đơn vị cấp dưới",
                "Chỉ tiêu được thống kê theo TTHC"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc",
                "- Đạt từ 80% trở lên sẽ đạt điểm tối đa.",
                "- Dưới 80% tính theo công thức:",
                "Tỷ lệ % hồ sơ TTHC tái sử dụng lại thông tin, dữ liệu*Điểm tối đa/80%."
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "4.4",
            "title": "Tỷ lệ hồ sơ TTHC được số hóa có kết nối, chia sẻ dữ liệu phục vụ tái sử dụng",
            "group": "4. Nhóm chỉ số về số hóa hồ sơ",
            "business": [
                "Số hồ sơ TTHC được số hóa có kết nối, đồng bộ với danh mục hồ sơ của cá nhân, tổ chức trên Cổng Dịch vụ công quốc gia: tổng số hồ sơ đồng bộ có ít nhất 1 file đính kèm trong thành phần hồ sơ được đánh dấu lấy từ kho dữ liệu cá nhân hoặc đồng bộ links kết quả giải quyết điện tử lên danh mục (Cổng DVCQG). BNĐP bổ sung dữ liệu đánh dấu thành phần hồ sơ lấy từ Cổng DVCQG.",
                "Tổng số hồ sơ TTHC thuộc thẩm quyền giải quyết: Tổng số hồ sơ có ngày tiếp nhận trong kỳ báo cáo (không tính hồ sơ không có ngày tiếp nhận)",
                "Chỉ tiêu được thống kê theo thời gian, theo TTHC và theo cơ quan, địa bàn:",
                "+ Bộ: tính trên hồ sơ có cơ quan thực hiện trực thuộc Bộ",
                "+ Tỉnh, xã: Tính trên hồ sơ có cơ quan thực hiện là Tỉnh/ xã tương ứng và các đơn vị cấp dưới",
                "Chỉ tiêu được thống kê theo TTHC",
                "Update : Trong TaiLieuNop có DuocLayTuKhoDMQG = 1 ngược lại là 0"
            ],
            "notes": [
                "Chưa có thông tin trong sheet."
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "4.5",
            "title": "Ứng dụng dữ liệu dân cư trong giải quyết thủ tục hành chính, cung cấp dịch vụ công",
            "group": "4. Nhóm chỉ số về số hóa hồ sơ",
            "business": [
                "Mẫu số : Tổng số TTHC thuộc thẩm quyền giải quyết của đơn vị được chọn, có đối tượng thực hiện là người dân",
                "Tỷ lệ TTHC triển khai kết nối, chia sẻ dữ liệu dân cư phục vụ giải quyết TTHC = Số TTHC có kết nối, chia sẻ dữ liệu dân cư phục vụ giải quyết TTHC/Tổng số TTHC có đối tượng thực hiện là người dân *100%.",
                "Số TTHC có kết nối, chia sẻ dữ liệu dân cư phục vụ giải quyết TTHC là Số TTHC có hồ sơ đồng bộ có “taikhoanduocxacthucvoiVNeID” hoặc “DuoclaytukhoDMQG”, “MaCSDL” của CSDL Dân cư.",
                "=> TaiKhoanDuocXacThucVoiVNeID = 1",
                "Tổng số TTHC có đối tượng thực hiện là người dân là Tổng số TTHC trên CSDL quốc gia về thủ tục hành chính có trường “đối tượng thực hiện” là “Công dân Việt Nam” hoặc “Người Việt Nam định cư ở nước ngoài” hoặc “Người nước ngoài”",
                "Cách tính:",
                "- Bộ: Tính theo số TTHC thuộc thẩm quyền giải quyết của Bộ (bao gồm các cơ quan ngành dọc).",
                "- Tỉnh: Tính theo số TTHC của tỉnh",
                "- Xã: Tính theo số TTHC cấp xã",
                "Tỷ lệ hồ sơ TTHC sử dụng thông tin, dữ liệu từ Cơ sở dữ liệu quốc gia về dân cư = Tổng số hồ sơ đồng bộ có “taikhoanduocxacthucvoiVNeID” hoặc “DuoclaytukhoDMQG”, “MaCSDL” của CSDL Dân cư/Tổng số hồ sơ TTHC * 100%",
                "Cách tính:",
                "- Bộ: Tính theo số hồ sơ TTHC thuộc thẩm quyền giải quyết của Bộ (bao gồm các cơ quan ngành dọc).",
                "- Tỉnh: Tính theo số hồ sơ TTHC của tỉnh (phân đến từng sở, ngành)",
                "- Xã: Tính theo số hồ sơ TTHC của xã"
            ],
            "notes": [
                "Chưa có thông tin trong sheet."
            ],
            "dataSources": [
                "Cơ sở dữ liệu quốc gia về TTHC",
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)"
            ]
        },
        {
            "id": "5.1",
            "title": "Tỷ lệ phản ánh, kiến nghị theo phân loại",
            "group": "5. Nhóm chỉ số về mức độ hài lòng",
            "business": [
                "- Tỷ lệ phản ánh, kiến nghị theo phân loại = Số phản ánh kiến nghị đã được tiếp nhận được phân loại theo Quy định, chính sách, thủ tục hoặc Hành vi của cán bộ công chức/ Tổng số PAKN trong kỳ theo đơn vị thống kê *100%"
            ],
            "notes": [
                "Chưa có thông tin trong sheet."
            ],
            "dataSources": [
                "Cổng DVCQG, Hệ thống PAKN"
            ]
        },
        {
            "id": "5.2",
            "title": "Tiến độ xử lý phản ánh, kiến nghị",
            "group": "5. Nhóm chỉ số về mức độ hài lòng",
            "business": [
                "Tỷ lệ phản ánh, kiến nghị xử lý đúng hạn PAKN, phân cách hàng nghìn bởi dấu chấm] ([Tỷ lệ phần trăm]%)ng dữ liệu hiển thị: [Số lượng PAKN, phân cách hàng nghìn bởi",
                "- Danh sách trạng thái đang xử lý: PAKN đã bổ sung, Phản ánh trực tiếp xử lý, xử lý ở địa phương, tiếp nhận ở địa phương, Đã gửi email,) trong tiến trình trong kỳ báo cáo: PAKN đã bổ sung, Phản ánh trực tiếp xử lý, xử lý ở địa phương, tiếp nhận ở địa phương, Đã gửi email, trả lại tiếp nhận địa phương trong trường hợp nội bộ chuyển trả đơn vị tiếp nhận",
                "- Danh sách trạng thái đã xử lý: BNĐP gửi trả lại BNĐP khác, BNĐP gửi trả VPCP, PAKN chờ công khai, PAKN đã công khai, Trả lại VPCP, Từ chối tiếp nhận, PAKN gửi đi đơn vị khác bằng phần mềm riêng, PA chờ bổ sung, Trả lại tiếp nhận địa phương trong trường hợp VPCP hoặc BNĐP chuyển trả lại",
                "Danh sách trạng thái chờ tiếp nhận: Tiếp nhận ở địa phương, Phản ánh đã bổ sung, Mới tiếp nhận VPCP",
                "- PAKN đang xử lý trong hạn:",
                "PAKN được coi là đang xử lý trong kỳ khi thời gian của bắt đầu của bước tương ứng với trạng thái đang xử lý, đã xử lý nằm trong kỳ hiện tại và thời gian kết thúc của bước đã xử lý sau kỳ hiện tại. Không tồn tại Ngày kết thúc tương ứng với trạng thái đã xử lý, đã công khai trong kỳ báo cáo.",
                "PAKN đang xử lý trong hạn nếu ngày cuối kỳ của kỳ báo cáo (hoặc ngày hiện tại đối với kỳ hiện tại) – Ngày bắt đầu của trạng thái chờ tiếp nhận trong kỳ <= 15 ngày làm việc.",
                "- PAKN đã xử lý đúng hạn: PAKN được coi là đã xử lý trong kỳ nếu thời gian kết thúc của bước tương ứng với trạng thái đã xử lý nằm trong kỳ báo cáo",
                "+ PAKN bị từ chối đúng hạn:",
                "TH1: PAKN được gửi trực tiếp BNĐP: Ngày từ chối <= Ngày gửi PAKN+ 2 ngày làm việc",
                "TH2: PAKN do VPCP hoặc BNĐP khác chuyển đến: Ngày chuyển trả VPCP, Ngày BNĐP gửi trả BNĐP <= Ngày VPCP, BNĐP chuyển gần nhất + 2 ngày làm việc",
                "+ PAKN yêu cầu bổ sung đúng hạn:",
                "TH1: PAKN được gửi trực tiếp đến BNĐP: Ngày yêu cầu bổ sung đầu tiên <= Ngày gửi PAKN + 5 ngày làm việc (không bao gồm các PAKN bị yêu cầu bổ sung sau khi Tiếp nhận)",
                "TH2: PAKN được VPCP, BNĐP chuyển đến: Ngày yêu cầu bổ sung đầu tiên gần nhất <= Ngày VPCP, BNĐP khác chuyển đến + 5 ngày làm việc",
                "(Chỉ xét trường hợp sau ngày yêu cầu bổ sung, không có ngày bắt đầu xử lý (tương ứng với trạng thái Đang xử lý, Đã xử lý) trong kỳ).",
                "+ PAKN xử lý đúng hạn:",
                "TH1: PAKN tiếp gửi trực tiếp đến BNĐP: Ngày bắt đầu xử lý của bước tương ứng với trạng thái chờ công khai, đã công khai <= Ngày CD/DN gửi PAKN + 15 ngày làm việc",
                "TH2: PAKN được chuyển từ VPCP, BNĐP khác: Ngày bắt đầu xử lý của bước tương ứng với trạng thái chờ công khai, đã công khai <= Ngày VPCP, BNĐP khác chuyển gần nhất + 15 ngày làm việc",
                "+ PAKN công khai đúng hạn: Ngày kết thúc của trạng thái công khai - Ngày bắt đầu chờ công khai/ đã công khai <=2 ngày làm việc. Nếu không có ngày kết thúc thì lấy theo ngày cuối kỳ báo cáo (lấy theo ngày hiện tại nếu thống kê kỳ hiện tại)",
                "Tổng số PAKN được tiếp nhận, xử lý trong kỳ= gồm tổng số PAKN được gửi tới đơn vị, đã và đang xử lý trong kỳ",
                "Trưng số PAKN được tiếp nhận, xử lý trong kỳ= gồm tổng số PAKN được gửi tới đơn"
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Cổng DVCQG, Hệ thống PAKN"
            ]
        },
        {
            "id": "5.3",
            "title": "Tỷ lệ hài lòng trong xử lý phản ánh, kiến nghị",
            "group": "5. Nhóm chỉ số về mức độ hài lòng",
            "business": [
                "Tỷ lệ hài lòng trong xử lý phản ánh, kiến nghị = (Tổng số PAKN – Số bị phản hồi trạng thái không hài lòng hoặc tiếp tục có phản ánh, kiến nghị về kết quả giải quyết hoặc quá hạn)/Tổng số phản ánh, kiến nghị *100%",
                "Số bị phản hồi trạng thái không hài lòng hoặc tiếp tục có phản ánh, kiến nghị về kết quả giải quyết hoặc quá hạn: là tổng số PAKN",
                "+ do dân đánh giá không hài lòng (có số dislike nhiều hơn like trên Cổng DVCQG)",
                "+ số PAKN giải quyết quá hạn (cách tính quá hạn theo chỉ tiêu 5c)",
                "+ PAKN bị nhắc lại trong nội dung PAKN sau đó có nội dung đánh giá không hài lòng (điều kiện này làm sau đợt tháng 4/2022) Liên quan đến việc cắt chuỗi AI -> kỹ thuật có làm được không?",
                "Tổng số PAKN= Tổng số PAKN có ngày tiếp nhận đầu tiên trong kỳ",
                "Xét các PAKN có Ngày tiếp nhận đầu tiên trong kỳ báo cáo, không bao gồm PAKN chưa được tiếp nhận. Trong mỗi kỳ báo cáo, mỗi PAKN được tính tối đa 1 lần.",
                "Không thống kê theo TTHC (ẩn khi chọn TTHC)",
                "Thống kê theo đơn vị: Bộ, Tỉnh, Xã"
            ],
            "notes": [
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc"
            ],
            "dataSources": [
                "Cổng DVCQG, Hệ thống PAKN"
            ]
        },
        {
            "id": "5.4",
            "title": "Tỷ lệ hài lòng trong tiếp nhận, giải quyết TTHC",
            "group": "5. Nhóm chỉ số về mức độ hài lòng",
            "business": [
                "=100%- (Tỷ lệ hồ sơ giải quyết quá hạn + Tỷ lệ hồ sơ TTHC có phản ánh, kiến nghị hoặc đánh giá dislike)."
            ],
            "notes": [
                "- Nếu mẫu số = 0: hiển thị 0 hoặc N/A theo quy định báo cáo",
                "- Làm tròn: đề xuất 2 chữ số thập phân (nếu hiển thị %)",
                "- Kỳ thống kê: theo khoảng thời gian chọn lọc",
                "- Đạt từ 90% trở lên sẽ đạt điểm tối đa.",
                "- Dưới 90% tính theo công thức:",
                "Tỷ lệ % hài lòng trong tiếp nhận, giải quyết TTHC*Điểm tối đa/90%."
            ],
            "dataSources": [
                "Hệ thống điều phối (Dữ liệu đồng bộ hồ sơ)",
                "Cổng DVCQG, Hệ thống PAKN"
            ]
        }
    ]
};
//# sourceMappingURL=formula-document.js.map