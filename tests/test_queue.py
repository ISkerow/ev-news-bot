from datetime import datetime, timedelta, timezone

import main


def make_manager():
    return main.QueueManager(bot=None, db=None)


def item(url, hours_ago=1):
    return {
        "url": url,
        "title_en": f"Title {url}",
        "published": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }


def test_queue_orders_newest_first():
    qm = make_manager()
    qm.put_news(item("https://a.com/old", hours_ago=10))
    qm.put_news(item("https://a.com/new", hours_ago=1))
    qm.put_news(item("https://a.com/mid", hours_ago=5))
    order = [qm.queue.get_nowait()[2]["url"] for _ in range(3)]
    assert order == ["https://a.com/new", "https://a.com/mid", "https://a.com/old"]


def test_queue_rejects_duplicates_and_skipped():
    qm = make_manager()
    assert qm.put_news(item("https://a.com/1"))
    assert not qm.put_news(item("https://a.com/1"))  # уже в очереди
    qm._mark_skipped("https://a.com/2")
    assert not qm.put_news(item("https://a.com/2"))  # отброшена как дубль истории


def test_skipped_set_does_not_grow_forever():
    qm = make_manager()
    for i in range(1100):
        qm._mark_skipped(f"https://a.com/{i}")
    assert len(qm.skipped) < 1000
