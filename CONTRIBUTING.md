# Contributing to Good News Scraper & Slider Generator

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 🚀 Quick Start for Contributors

### 1. Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/mounseflit/GoodNews.git
cd GoodNews

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Test the installation
python test_integration.py
```

### 2. Code Style

We follow Python best practices:

- **PEP 8** for code style
- **Type hints** for function signatures
- **Docstrings** for all public functions
- **Clear variable names** and comments

Example:
```python
async def get_positive_news(create_sliders: bool = True) -> Dict[str, Any]:
    """
    Fetch positive news articles from Morocco and optionally create sliders.
    
    Args:
        create_sliders: Whether to create sliders from the articles
        
    Returns:
        Dictionary containing articles, count, and optional slider results
    """
```

### 3. Testing

Always test your changes:

```bash
# Test basic functionality
python test_integration.py

# Test specific components
python -c "from api.news import SliderAPIClient; print('✅ Import successful')"

# Test API endpoints
curl "http://localhost:8000/api/health"
```

## 📋 Areas for Contribution

### 🔍 High Priority
- **Additional News Sources**: Add support for more Moroccan news websites
- **Error Handling**: Improve error messages and recovery mechanisms
- **Performance**: Optimize API response times and caching
- **Documentation**: Improve API documentation and examples

### 🌟 Feature Requests
- **Multi-language Support**: Support for Arabic and French news
- **Scheduled Execution**: Cron-like scheduling for automatic news updates
- **Analytics Dashboard**: Web interface showing news trends and statistics
- **Webhook Integration**: Real-time notifications for new articles
- **Image Enhancement**: AI-powered image optimization for sliders

### 🐛 Known Issues
- Server stability improvements for long-running processes
- Better handling of rate limits from news sources
- Enhanced image download reliability

## 🔧 Development Guidelines

### Code Organization

```
api/
├── news.py              # Main application logic
├── models/              # Data models (future)
├── services/            # Business logic (future)
└── utils/               # Helper functions (future)
```

### Adding New Features

1. **Create a new branch**: `git checkout -b feature/your-feature`
2. **Write tests first**: Test-driven development preferred
3. **Implement the feature**: Follow existing code patterns
4. **Update documentation**: Add to README if user-facing
5. **Test thoroughly**: Ensure no breaking changes

### API Endpoint Guidelines

- Use clear, descriptive endpoint names
- Follow REST conventions
- Include proper error handling
- Add request/response examples
- Version your APIs (`/api/v1/`)

Example:
```python
@app.get("/api/v1/news", response_model=NewsResponse)
async def get_news(
    create_sliders: bool = Query(True, description="Create sliders from articles"),
    source: Optional[str] = Query(None, description="Filter by news source")
) -> NewsResponse:
    """Get latest positive news articles with optional slider creation."""
```

## 📝 Pull Request Process

### Before Submitting

1. **Check existing issues**: Avoid duplicate work
2. **Fork the repository**: Work on your own fork
3. **Create feature branch**: Don't work on main/master
4. **Test your changes**: Ensure everything works
5. **Update documentation**: Include relevant updates

### PR Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
- [ ] Tested locally
- [ ] Added new tests
- [ ] All existing tests pass

## Screenshots (if applicable)
Add screenshots for UI changes.

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes
```

### Review Process

1. **Automated checks**: CI/CD runs tests automatically
2. **Code review**: Maintainers review your code
3. **Feedback**: Address any requested changes
4. **Approval**: PR gets approved and merged

## 🐛 Bug Reports

### Good Bug Reports Include:

1. **Clear title**: Descriptive summary of the issue
2. **Environment**: OS, Python version, dependency versions
3. **Steps to reproduce**: Exact steps that cause the bug
4. **Expected behavior**: What should happen
5. **Actual behavior**: What actually happens
6. **Logs/errors**: Any error messages or stack traces

### Bug Report Template:

```markdown
**Bug Description**
A clear description of the bug.

**Environment**
- OS: [e.g., Windows 10, Ubuntu 20.04]
- Python: [e.g., 3.11.0]
- FastAPI: [e.g., 0.104.1]

**Steps to Reproduce**
1. Configure environment with...
2. Run command...
3. Access endpoint...
4. See error

**Expected Behavior**
Description of expected behavior.

**Actual Behavior**
Description of actual behavior.

**Logs**
```
Error logs here
```

**Additional Context**
Any other relevant information.
```

## 🌟 Feature Requests

### Good Feature Requests Include:

1. **Problem statement**: What problem does this solve?
2. **Proposed solution**: How would you implement it?
3. **Use case**: Real-world scenarios where this helps
4. **Alternatives**: Other solutions you've considered

### Feature Request Template:

```markdown
**Feature Description**
Clear description of the proposed feature.

**Problem Statement**
What problem does this feature solve?

**Proposed Solution**
Detailed description of the implementation.

**Use Cases**
- Use case 1: Description
- Use case 2: Description

**Alternatives Considered**
- Alternative 1: Description
- Alternative 2: Description

**Additional Context**
Any other relevant information.
```

## 📚 Documentation Guidelines

### Code Documentation

- **Functions**: Include docstrings with parameters and return values
- **Classes**: Describe purpose and usage
- **Modules**: Include module-level documentation
- **Complex logic**: Add inline comments

### README Updates

- Keep examples current and working
- Include new configuration options
- Update API documentation
- Add troubleshooting sections for new features

### API Documentation

- Use FastAPI's automatic documentation features
- Include request/response examples
- Document all parameters and their types
- Provide error response examples

## 🔒 Security Guidelines

### API Keys and Secrets

- Never commit API keys or passwords
- Use environment variables for all secrets
- Include security notes in documentation
- Rotate keys regularly

### Code Security

- Validate all user inputs
- Use secure HTTP methods
- Implement proper error handling (don't expose internals)
- Follow OWASP guidelines for web applications

## 🤝 Community Guidelines

### Be Respectful

- Use inclusive language
- Be patient with newcomers
- Provide constructive feedback
- Help others learn and grow

### Communication

- Use clear, professional language
- Provide context for decisions
- Ask questions when unsure
- Share knowledge and resources

## 📞 Getting Help

### Before Asking for Help

1. Check existing documentation
2. Search closed issues
3. Try debugging with logs
4. Prepare a minimal reproducible example

### Where to Ask

- **General questions**: GitHub Discussions
- **Bug reports**: GitHub Issues
- **Feature requests**: GitHub Issues
- **Security issues**: Email maintainers directly

### Help Others

- Answer questions in discussions
- Review pull requests
- Improve documentation
- Share your use cases and solutions

---

Thank you for contributing to the Good News Scraper & Slider Generator! Your contributions help make positive news more accessible and automated content creation easier for everyone. 🌟