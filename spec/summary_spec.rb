require 'summary'

TEST_SUMMARY = %q(
- question: "Does Vitamin C help with colds?"
  answer: "No."
  url: "http://cochranelibrary-wiley.com/doi/10.1002/14651858.CD000980.pub4/abstract"
  notes: |
    Regular supplementation seems to modestly shorten how long your cold is, but it doesn't make you less likely to get sick in the first place.
)

describe Summary do
  describe ".unmarshal" do
    it "can unmarshal YAML summaries" do
      summaries = Summary.unmarshal(TEST_SUMMARY)

      s = summaries.first
      expect(s.question).to eq("Does Vitamin C help with colds?")
      expect(s.answer).to eq("No.")
    end
  end
end
