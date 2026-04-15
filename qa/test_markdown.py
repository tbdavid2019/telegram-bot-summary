import markdown
print("Standard #tag:")
print(markdown.markdown("#tag"))

print("\nEscaped \\#tag:")
print(markdown.markdown("\#tag"))

print("\nPython literal \\\\#tag:")
print(markdown.markdown("\\#tag"))
