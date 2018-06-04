require 'yaml'

class Summary
  def self.unmarshal(str)
    summary_array = YAML.load(str)

    result = []

    summary_array.each do |s|
      result << Summary.new(
        question: s.fetch("question"),
        answer: s.fetch("answer"),
        url: s.fetch("url"),
        notes: s["notes"],
      )
    end

    return result
  end

  attr_accessor :question, :answer, :url, :notes

  def initialize(args)
    @question = args[:question]
    @answer = args[:answer]
    @url = args[:url]
    @notes = args[:notes]
  end
end
