require 'erb'

class Renderer
  attr_reader :template

  def initialize(args)
    @template = args.fetch(:template)
    @summaries = args.fetch(:summaries)
  end

  def render(options = {})
    ERB.new(template).result(binding)
  end
end
