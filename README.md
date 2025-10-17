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

## Collaboration Workflows

This project supports two development workflows:

### 1. GitHub Web Interface (No Installation Required)

Perfect for quick edits and non-technical collaborators:

1. **Edit files directly on GitHub:**
   - Navigate to any file in the `src/` directory
   - Click the pencil icon to edit
   - Make your changes
   - Commit to a new branch and create a pull request

2. **Automatic validation:**
   - GitHub Actions will automatically build your changes
   - Check the PR for a green checkmark (build succeeded) or red X (build failed)
   - The bot will comment with build stats and preview instructions

3. **Preview your changes:**
   - Download the `story-preview` artifact from the Actions tab
   - Extract and open `index.html` to test your story
   - No local setup required!

4. **Merge when ready:**
   - Once approved, merge the PR
   - Your changes will be live on GitHub Pages within minutes

### 2. Local Development (Desktop Flow)

For more complex work and offline development:

#### Prerequisites

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

#### Download Story Formats

```bash
mkdir -p storyformats && cd storyformats

# Download tweego which includes story formats
wget https://github.com/tmedwards/tweego/releases/download/v2.1.1/tweego-2.1.1-linux-x64.zip
unzip tweego-2.1.1-linux-x64.zip
mv storyformats/* .
cd ..
```

#### Build Scripts

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

#### Git Workflow

```bash
# Create a feature branch
git checkout -b add-new-chapter

# Make your changes to files in src/
# Test locally with npm run dev

# Commit and push
git add src/
git commit -m "Add new chapter"
git push -u origin add-new-chapter

# Create a pull request on GitHub
gh pr create --title "Add new chapter" --body "Adds chapter 2"
```

## Deployment

### Automatic Deployment

The project uses GitHub Actions to automatically build and deploy to GitHub Pages on every push to `main`.

**What happens on PRs:**
- ✅ Build validation runs automatically
- ✅ Build artifacts are uploaded for download and testing
- ✅ Bot comments on PR with build stats and preview instructions
- ❌ No live PR preview URL (GitHub Pages limitation - only deploys from `main`)

**What happens on `main` branch:**
- ✅ Build validation runs
- ✅ Automatic deployment to GitHub Pages
- ✅ Live at the production URLs within 1-2 minutes

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
