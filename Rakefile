folder = File.expand_path("./lib", __dir__)
$:.unshift(folder)

require 'app'

task :default do
  a = App.new("summaries.yml", "template.haml")
  a.render_and_save("docs/index.html")

  `git add docs`
  `git commit -m "-- Site build --"`
  `git push`
end

task :build do
  a = App.new("summaries.yml", "template.haml")
  a.render_and_save("docs/index.html")
end
