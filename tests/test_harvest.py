from harvest import oai_pmh


class FakeRecord:
    def __init__(self, xml: str):
        self.raw = xml


def test_harvest_records_normalizes_datacite(monkeypatch):
    datacite_xml = """
    <record xmlns:oai="http://www.openarchives.org/OAI/2.0/" xmlns:d="http://datacite.org/schema/kernel-4">
      <oai:header><oai:identifier>oai:zenodo.org:1234</oai:identifier></oai:header>
      <oai:metadata>
        <d:resource>
          <d:title>Sample Title</d:title>
          <d:creator><d:creatorName>Ada Lovelace</d:creatorName></d:creator>
          <d:subject>math</d:subject>
          <d:description>desc</d:description>
          <d:publicationYear>2024</d:publicationYear>
          <d:identifier identifierType="URL">https://example.org/rec/1</d:identifier>
          <d:identifier identifierType="DOI">10.1234/example</d:identifier>
        </d:resource>
      </oai:metadata>
    </record>
    """

    class FakeList:
        def __iter__(self):
            return iter([FakeRecord(datacite_xml)])

    class FakeSickle:
        def __init__(self, *_args, **_kwargs):
            pass

        def ListRecords(self, **_kwargs):
            return FakeList()

    monkeypatch.setattr(oai_pmh, "Sickle", FakeSickle)

    out = oai_pmh.harvest_records(base_url="http://fake", limit=1)
    assert out[0]["id"] == "10.1234/example"
    assert out[0]["title"] == "Sample Title"
    assert out[0]["creators"] == "Ada Lovelace"
    assert out[0]["url"] == "https://example.org/rec/1"


def test_harvest_records_falls_back_to_dc(monkeypatch):
    dc_xml = """
    <record xmlns:oai="http://www.openarchives.org/OAI/2.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <oai:header><oai:identifier>oai:example:1</oai:identifier></oai:header>
      <oai:metadata>
        <dc:title>DC Title</dc:title>
        <dc:creator>Someone</dc:creator>
        <dc:subject>Topic</dc:subject>
        <dc:description>DC desc</dc:description>
        <dc:date>2023-01-01</dc:date>
        <dc:identifier>https://example.org/dc/1</dc:identifier>
      </oai:metadata>
    </record>
    """

    class FakeList:
        def __iter__(self):
            return iter([FakeRecord(dc_xml)])

    class FakeSickle:
        def __init__(self, *_args, **_kwargs):
            pass

        def ListRecords(self, **_kwargs):
            return FakeList()

    monkeypatch.setattr(oai_pmh, "Sickle", FakeSickle)

    out = oai_pmh.harvest_records(base_url="http://fake", limit=1)
    assert out[0]["title"] == "DC Title"
    assert out[0]["id"] == "oai:example:1"
    assert out[0]["subjects"] == "Topic"
    assert out[0]["description"] == "DC desc"
