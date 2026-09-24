Your previous reply did not match the required JSON output. Return only the corrected JSON object, with no prose and no code fences.
{%- if errors %}

Validation errors:
{%- for error in errors %}
- {{ error }}
{%- endfor %}
{%- endif %}

<previous_output>
{{ previous }}
</previous_output>
