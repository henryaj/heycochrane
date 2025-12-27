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
    engine = Haml::Engine.new(template)
    summaries_json = Summary.to_json_array(@summaries)
    tag_metadata_json = Summary.tag_metadata_json
    engine.render(Object.new, {
      summaries: @summaries,
      summaries_json: summaries_json,
      tag_metadata_json: tag_metadata_json
    })
  end
end
