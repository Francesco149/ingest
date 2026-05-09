# tasks/describe_manga_page

## Purpose
Describes sequences of manga manga pages using a vision-capable LLM for semantic search.

## Pool
vision

## Input
```
image_paths    List[str]  list of paths to the images to describe
url            str       original source URL
url_slug       str       original source slug (mandatory)
custom_prompt  str       (optional) custom prompt for the vision model
metadata       dict      (optional) metadata from manga
start_page     int       starting page number
end_page       int       ending page number
```

## Output
```
descriptions   list[dict] the generated descriptions
url            str       original source URL
url_slug       str       original source slug (mandatory)
```

## Creates
Nothing.

## Behavior Rules
- Uses an OpenAI-compatible chat completion endpoint with a specialized prompt for sequences of pages.
- Prompt text comes from `config["prompts"]["manga_describe"]`.
- PNG files are sent directly as base64 data URLs; JPEG files are converted to
  temporary PNG files before encoding.
- On exception: any temporary files are cleaned up and the exception is re-raised.
