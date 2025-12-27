require 'haml'
require_relative 'summary'

class Renderer
  attr_reader :template, :summaries

  def initialize(args)
    @template = args.fetch(:template)
    @summaries = args.fetch(:summaries)
    Summary.load_tag_metadata(args[:tags_path] || 'tags.yml')
  end

  def render(options = {})
    summaries_json = Summary.to_json_array(@summaries)
    tag_metadata_json = Summary.tag_metadata_json
    locals = {
      summaries: @summaries,
      summaries_json: summaries_json,
      tag_metadata_json: tag_metadata_json
    }
    Haml::Template.new { template }.render(Object.new, locals)
  end
end
