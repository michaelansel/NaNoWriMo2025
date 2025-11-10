/*
 * AllPaths Story Format
 * A simple format that outputs the story HTML for post-processing by generator.py
 */

window.storyFormat({
    name: "AllPaths",
    version: "1.0.0",
    author: "NaNoWriMo2025",
    description: "Generates all possible story paths for AI-based continuity checking",
    proofing: true,
    source: `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{STORY_NAME}}</title>
    <style>
        body {
            font-family: monospace;
            padding: 2rem;
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            color: #667eea;
        }
        .info {
            background: #f0f0f0;
            padding: 1rem;
            border-radius: 4px;
            margin: 1rem 0;
        }
    </style>
</head>
<body>
    <h1>{{STORY_NAME}} - AllPaths Format</h1>
    <div class="info">
        <p><strong>This is an intermediate file.</strong></p>
        <p>Run the AllPaths generator to create the full output:</p>
        <pre>python3 formats/allpaths/generator.py &lt;this-file&gt; &lt;output-dir&gt;</pre>
    </div>
    {{STORY_DATA}}
</body>
</html>`
});
