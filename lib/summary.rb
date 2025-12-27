require 'yaml'
require 'json'

class Summary
  @@tag_metadata = nil

  def self.load_tag_metadata(path = 'tags.yml')
    @@tag_metadata = YAML.load(File.read(path))
  end

  def self.tag_metadata
    @@tag_metadata || {}
  end

  def self.unmarshal(str)
    summary_array = YAML.load(str)

    result = []

    summary_array.each do |s|
      result << Summary.new(
        question: s.fetch("question"),
        answer: s.fetch("answer"),
        url: s.fetch("url"),
        notes: s["notes"],
        interest: s["interest"],
        tags: s["tags"] || [],
      )
    end

    return result
  end

  def self.to_json_array(summaries)
    summaries.map { |s| s.to_hash }.to_json
  end

  def self.tag_metadata_json
    tag_metadata.to_json
  end

  attr_accessor :question, :answer, :url, :notes, :interest, :tags

  def initialize(args)
    @question = args[:question]
    @answer = args[:answer]
    @url = args[:url]
    @notes = args[:notes]
    @interest = args[:interest]
    @tags = args[:tags] || []
  end

  def to_hash
    {
      question: @question,
      answer: @answer,
      url: @url,
      notes: @notes,
      interest: @interest,
      tags: @tags
    }
  end
end
