const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const suggestionsDiv = document.getElementById('suggestions');
const loadingDiv = document.getElementById('loading');
let abortController = null;

// Focus on search input when page loads
document.addEventListener('DOMContentLoaded', () => {
    searchInput.focus();
});

// Add base URL configuration at the top
const BASE_URL = 'https://test.app.com';

// Add URL parameter handling utility function
function replaceUrlParams(url, params = {}) {
    // Default params if not provided
    const defaultParams = {
        id: '0', // Default ID if not specified
        // Add more default params as needed
    };
    
    // Combine default params with provided params
    const finalParams = { ...defaultParams, ...params };
    
    // Replace each parameter in the URL
    return url.replace(/:(\w+)/g, (match, param) => {
        return finalParams[param] || match;
    });
}

// Function to show loading state
function showLoading() {
    loadingDiv.style.display = 'block';
    suggestionsDiv.style.display = 'none';
}

// Function to hide loading state
function hideLoading() {
    loadingDiv.style.display = 'none';
}

// Function to perform the search
function performSearch() {
    // Cancel any ongoing request
    if (abortController) {
        abortController.abort();
    }

    const query = searchInput.value.trim();
    if (query.length === 0) {
        suggestionsDiv.style.display = 'none';
        return;
    }

    showLoading();
    fetchSuggestions(query);
}

// Handle input to hide suggestions when empty
searchInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    if (query.length === 0) {
        suggestionsDiv.style.display = 'none';
    }
});

// Handle button click
searchButton.addEventListener('click', performSearch);

// Handle Enter key
searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        performSearch();
    }
});

function fetchSuggestions(query) {
    // Create new AbortController for this request
    abortController = new AbortController();
    const signal = abortController.signal;

    fetch(`http://localhost:8000/ask?query=${encodeURIComponent(query)}`, { signal })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            // Pass the entire response object to displaySuggestions
            displaySuggestions(data);
        })
        .catch(error => {
            // Don't show error if the request was aborted
            if (error.name === 'AbortError') {
                return;
            }
            console.error('Error:', error);
            hideLoading();
            suggestionsDiv.innerHTML = '<div class="suggestion-item">Error fetching suggestions</div>';
            suggestionsDiv.style.display = 'block';
        });
}

function displaySuggestions(response) {
    suggestionsDiv.innerHTML = '';
    // Debug log to see the response structure
    console.log('Response received:', response);
    let explanation = '';
    // Check if response is a string (old format) or object (new format)
    if (typeof response === 'string') {
        if (response === 'No matching pages found') {
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No matching pages found</div>';
            suggestionsDiv.style.display = 'block';
            return;
        }
        // Parse the old format response
        const matches = response.match(/Suggested (?:page|pages): (.*)/);
        if (!matches) {
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No matching pages found</div>';
            suggestionsDiv.style.display = 'block';
            return;
        }
        const suggestions = matches[1].split(', ');
        suggestions.forEach(suggestion => {
            const parts = suggestion.split(' - ');
            if (parts.length < 3) return;
            const title = parts[0];
            const relativeUrl = parts[1];
            const description = parts.slice(2).join(' - ').replace(/Tags:.*$/, '').trim();
            createSuggestionItem(title, relativeUrl, description);
        });
    } else {
        // Handle new JSON format
        // Check if we have the expected nested structure
        if (response && response.llm_response && response.llm_response.suggestions) {
            const suggestions = response.llm_response.suggestions;
            explanation = response.llm_response.explanation || '';
            if (suggestions.length === 0) {
                suggestionsDiv.innerHTML = '<div class="suggestion-item">No matching pages found</div>';
                suggestionsDiv.style.display = 'block';
            } else {
                suggestions.forEach(suggestion => {
                    if (suggestion.title && suggestion.url && suggestion.description) {
                        createSuggestionItem(suggestion.title, suggestion.url, suggestion.description);
                    }
                });
            }
        } else {
            // If the structure is not as expected, show no matches
            suggestionsDiv.innerHTML = '<div class="suggestion-item">No matching pages found</div>';
            suggestionsDiv.style.display = 'block';
        }
    }
    // Show explanation if present
    if (explanation) {
        const explanationDiv = document.createElement('div');
        explanationDiv.className = 'explanation';
        explanationDiv.textContent = explanation;
        suggestionsDiv.appendChild(explanationDiv);
    }
    suggestionsDiv.style.display = 'block';
}

function createSuggestionItem(title, relativeUrl, description) {
    // Process the URL: add base URL and replace parameters
    const fullUrl = `${BASE_URL}${replaceUrlParams(relativeUrl)}`;
    
    const suggestionItem = document.createElement('div');
    suggestionItem.className = 'suggestion-item';
    
    // Create a container for the title and description
    const contentDiv = document.createElement('div');
    contentDiv.className = 'suggestion-content';
    
    // Add the title as a link with the processed URL
    const titleLink = document.createElement('a');
    titleLink.href = fullUrl;
    titleLink.target = "_blank";
    titleLink.textContent = title;
    titleLink.className = 'suggestion-title';
    
    // Add the description
    const descElement = document.createElement('p');
    descElement.className = 'suggestion-description';
    descElement.textContent = description;
    
    // Add the URL display (optional - remove if you don't want to show the URL)
    const urlElement = document.createElement('p');
    urlElement.className = 'suggestion-url';
    urlElement.textContent = fullUrl;
    
    contentDiv.appendChild(titleLink);
    contentDiv.appendChild(descElement);
    contentDiv.appendChild(urlElement);
    suggestionItem.appendChild(contentDiv);
    suggestionsDiv.appendChild(suggestionItem);
}

// Close suggestions when clicking outside
document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !suggestionsDiv.contains(e.target) && !searchButton.contains(e.target)) {
        suggestionsDiv.style.display = 'none';
    }
}); 