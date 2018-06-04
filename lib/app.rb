require 'renderer'
require 'summary'

class App
  attr_reader :summaries_path, :template_path

  def initialize(summaries_path, template_path)
    @summaries_path = summaries_path
    @template_path = template_path
  end

  def render_and_save(path)
    t = File.read(template_path)
    s = File.read(summaries_path)

    summaries = Summary.unmarshal(s)

    r = Renderer.new(template: t, summaries: summaries)
    html = r.render

    File.write(path, html)
  end
end
