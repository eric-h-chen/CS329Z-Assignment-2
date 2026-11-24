from conftest import event, merchant

REPORT_HEADER = ["merchant_id", "settlement_date", "currency", "gross_minor",
                 "refunds_minor", "fees_minor", "net_minor", "payment_count"]


def test_report_header(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert list(report[0]) == REPORT_HEADER


def test_memo_punctuation(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z",
              memo="Smith, J."),
        event(102, "T2", "payment", "MRC-T001", "20.00", "USD", "2026-03-10T19:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "3000"
    assert report[0]["payment_count"] == "2"


def test_single_payment(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert report == [{
        "merchant_id": "MRC-T001", "settlement_date": "2026-03-10", "currency": "USD",
        "gross_minor": "1000", "refunds_minor": "0", "fees_minor": "30",
        "net_minor": "970", "payment_count": "1",
    }]


def test_merchant_id_nbsp(run):
    report, rejects = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001 ", "10.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert report[0]["merchant_id"] == "MRC-T001"
    assert rejects == []


def test_event_sequence(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(998, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
        event(1002, "T1", "payment", "MRC-T001", "25.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "2500"


def test_pending_only(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z",
              status="pending"),
    ])
    assert report == []


def test_row_order(run):
    merchants = [merchant("MRC-B002"), merchant("MRC-A001")]
    report, _ = run("2026-03", merchants, [
        event(101, "T1", "payment", "MRC-B002", "10.00", "USD", "2026-03-11T18:00:00Z"),
        event(102, "T2", "payment", "MRC-A001", "10.00", "USD", "2026-03-12T18:00:00Z"),
        event(103, "T3", "payment", "MRC-B002", "10.00", "USD", "2026-03-10T18:00:00Z"),
        event(104, "T4", "payment", "MRC-A001", "10.00", "USD", "2026-03-11T18:00:00Z"),
    ])
    assert [(r["merchant_id"], r["settlement_date"]) for r in report] == [
        ("MRC-A001", "2026-03-11"), ("MRC-A001", "2026-03-12"),
        ("MRC-B002", "2026-03-10"), ("MRC-B002", "2026-03-11"),
    ]


def test_merchant_sort_order(run):
    merchants = [merchant("MRC-10"), merchant("MRC-9")]
    report, _ = run("2026-03", merchants, [
        event(101, "T1", "payment", "MRC-10", "10.00", "USD", "2026-03-10T18:00:00Z"),
        event(102, "T2", "payment", "MRC-9", "10.00", "USD", "2026-03-10T19:00:00Z"),
    ])
    assert [r["merchant_id"] for r in report] == ["MRC-9", "MRC-10"]

def test_reversal(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
        event(102, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z",
              status="reversed"),
    ])
    assert report == []


def test_fx_weekday(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "EUR", "2026-03-10T18:00:00Z"),
    ], rates=[("2026-03-09", "EUR", "USD", "1.080000"),
              ("2026-03-10", "EUR", "USD", "1.090000"),
              ("2026-03-11", "EUR", "USD", "1.100000")])
    assert report[0]["gross_minor"] == "1090"
    assert report[0]["fees_minor"] == "33"


def test_unknown_merchant_rejected(run):
    report, rejects = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "mrc-t001", "10.00", "USD", "2026-03-10T18:00:00Z"),
        event(102, "T2", "payment", "MRC-X999", "10.00", "USD", "2026-03-10T19:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "1000"
    assert rejects == [{"event_seq": "102", "txn_id": "T2", "reason": "UNKNOWN_MERCHANT"}]


def test_local_date(run):
    report, _ = run("2026-03", [merchant("MRC-T001", tz="Asia/Tokyo")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T15:30:00Z"),
    ])
    assert report[0]["settlement_date"] == "2026-03-11"


def test_failed_payment(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z",
              status="pending"),
        event(102, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z",
              status="failed"),
    ])
    assert report == []


def test_yen_amount(run):
    report, _ = run("2026-03", [merchant("MRC-T001", tz="Asia/Tokyo", ccy="JPY")], [
        event(101, "T1", "payment", "MRC-T001", "1200", "JPY", "2026-03-10T03:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "1200"


def test_reversed_then_settled(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
        event(102, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z",
              status="reversed"),
        event(103, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "1000"


def test_refund_same_day(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "20.00", "USD", "2026-03-10T17:00:00Z"),
        event(102, "T2", "refund", "MRC-T001", "5.00", "USD", "2026-03-10T19:00:00Z",
              original="T1"),
    ])
    assert report[0]["gross_minor"] == "2000"
    assert report[0]["refunds_minor"] == "500"
    assert report[0]["net_minor"] == "1440"


def test_fx_weekend(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "EUR", "2026-03-14T18:00:00Z"),
    ], rates=[("2026-03-13", "EUR", "USD", "1.090000"),
              ("2026-03-16", "EUR", "USD", "1.100000")])
    assert report[0]["gross_minor"] == "1090"


def test_fx_tokyo_merchant(run):
    report, _ = run("2026-03", [merchant("MRC-T001", tz="Asia/Tokyo")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "EUR", "2026-03-16T16:00:00Z"),
    ], rates=[("2026-03-16", "EUR", "USD", "1.090000"),
              ("2026-03-17", "EUR", "USD", "1.100000")])
    assert report[0]["settlement_date"] == "2026-03-17"
    assert report[0]["gross_minor"] == "1090"

def test_two_payments_totals(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T17:00:00Z"),
        event(102, "T2", "payment", "MRC-T001", "20.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "3000"
    assert report[0]["fees_minor"] == "90"


def test_small_payment_fees(run):
    report, _ = run("2026-03", [merchant("MRC-T001", bps=290)], [
        event(101, "T1", "payment", "MRC-T001", "0.17", "USD", "2026-03-10T17:00:00Z"),
        event(102, "T2", "payment", "MRC-T001", "0.17", "USD", "2026-03-10T18:00:00Z"),
        event(103, "T3", "payment", "MRC-T001", "0.17", "USD", "2026-03-10T19:00:00Z"),
    ])
    assert report[0]["gross_minor"] == "51"
    assert report[0]["fees_minor"] == "0"


def test_out_dir_created(run, tmp_path):
    run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "10.00", "USD", "2026-03-10T18:00:00Z"),
    ])
    assert (tmp_path / "out" / "2026-03" / "report.csv").is_file()
    assert (tmp_path / "out" / "2026-03" / "rejects.csv").is_file()


def test_refund_other_day(run):
    report, _ = run("2026-03", [merchant("MRC-T001")], [
        event(101, "T1", "payment", "MRC-T001", "20.00", "USD", "2026-03-10T18:00:00Z"),
        event(102, "T2", "refund", "MRC-T001", "5.00", "USD", "2026-03-12T18:00:00Z",
              original="T1"),
    ])
    assert len(report) == 2
    assert report[1]["settlement_date"] == "2026-03-12"
    assert report[1]["refunds_minor"] == "500"
    assert report[1]["payment_count"] == "0"


def test_empty_input(run, tmp_path):
    report, rejects = run("2026-03", [merchant("MRC-T001")], [])
    assert report == []
    assert rejects == []
    out = tmp_path / "out" / "2026-03"
    assert (out / "report.csv").read_text(encoding="utf-8").splitlines() == [",".join(REPORT_HEADER)]
    assert (out / "rejects.csv").read_text(encoding="utf-8").splitlines() == ["event_seq,txn_id,reason"]
