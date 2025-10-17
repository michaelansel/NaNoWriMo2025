# NaNoWriMo2025

Interactive fiction project built with [Tweego](https://www.motoslave.net/tweego/) and deployed to GitHub Pages.

## Project Structure

```
NaNoWriMo2025/
├── src/                    # Twee 3 source files
│   ├── StoryData.twee     # Story metadata
│   ├── StoryTitle.twee    # Story title
│   └── Start.twee         # Story passages
├── .github/workflows/     # GitHub Actions CI/CD
└── dist/                  # Build output (ignored by git)
```

## Development

### Prerequisites

Install [Tweego](https://github.com/tmedwards/tweego/releases) for local development:

**macOS:**
```bash
wget https://github.com/tmedwards/tweego/releases/download/v2.1.1/tweego-2.1.1-macos-x64.zip
unzip tweego-2.1.1-macos-x64.zip
chmod +x tweego
sudo mv tweego /usr/local/bin/
```

**Linux:**
```bash
wget https://github.com/tmedwards/tweego/releases/download/v2.1.1/tweego-2.1.1-linux-x64.zip
unzip tweego-2.1.1-linux-x64.zip
chmod +x tweego
sudo mv tweego /usr/local/bin/
```

**Windows:**
Download from [releases page](https://github.com/tmedwards/tweego/releases) and add to PATH.

### Download Story Formats

```bash
mkdir -p storyformats && cd storyformats

# Harlowe
wget https://github.com/klembot/harlowe/releases/download/3.3.9/harlowe-3.3.9.zip
unzip harlowe-3.3.9.zip && rm harlowe-3.3.9.zip

# Paperthin
wget https://github.com/BenjaminSiskoo/Paperthin/raw/master/paperthin-1.0.0.zip
unzip paperthin-1.0.0.zip && rm paperthin-1.0.0.zip
```

### Build Scripts

```bash
# Build both versions
npm run build

# Build main version only (Harlowe)
npm run build:main

# Build proofread version only (Paperthin)
npm run build:proofread

# Watch mode for development (Harlowe)
npm run dev

# Watch mode for proofread version (Paperthin)
npm run dev:proofread

# Clean build directory
npm run clean
```

## Deployment

The project uses GitHub Actions to automatically build and deploy to GitHub Pages on every push to `main`.

### Setup GitHub Pages

1. Create the repository on GitHub
2. Push your code to the `main` branch
3. Go to repository Settings → Pages
4. Set Source to "GitHub Actions"
5. The workflow will automatically deploy

### Published URLs

- **Main story (Harlowe):** `https://[username].github.io/NaNoWriMo2025/`
- **Proofread version (Paperthin):** `https://[username].github.io/NaNoWriMo2025/proofread.html`

## Story Formats

- **Harlowe 3.3.9:** Main interactive fiction format with rich features
- **Paperthin 1.0.0:** Linear proofreading format that displays all passages in sequence

## Writing

Add new passages to files in the `src/` directory using [Twee 3 notation](https://github.com/iftechfoundation/twine-specs/blob/master/twee-3-specification.md):

```twee
:: Passage Name [tag1 tag2]
Passage content here.

[[Link to another passage->OtherPassage]]
```

## Resources

- [Tweego Documentation](https://www.motoslave.net/tweego/docs/)
- [Twee 3 Specification](https://github.com/iftechfoundation/twine-specs/blob/master/twee-3-specification.md)
- [Harlowe Documentation](https://twine2.neocities.org/)
- [Modern Twine Workflow Guide](https://dev.to/lazerwalker/a-modern-developer-s-workflow-for-twine-4imp)

## License

ISC
