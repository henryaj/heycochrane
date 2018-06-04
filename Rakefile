folder = File.expand_path("./lib", __dir__)
$:.unshift(folder)

require 'app'

task :default do
  a = App.new("summaries.yml", "template.html")
  a.render_and_save("docs/index.html")

  `git add docs`
  `git commit -m "-- Site build --"`
  `git push`
end
