require 'haml'

class Renderer
  attr_reader :template, :summaries

  def initialize(args)
    @template = args.fetch(:template)
    @summaries = args.fetch(:summaries)
  end

  def render(options = {})

    engine = Haml::Engine.new(template)
    engine.render(Object.new, {summaries: @summaries})
  end
end
