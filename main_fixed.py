The provided code and log files include a relatively large and complex system, typically used for monitoring and controlling devices using MQTT, HTTP, and several APIs. Based on the provided `main.py`, `shared_data.py`, and `heatpump.py`, and noting issues logged in the `Recent logs`, let's go through a comprehensive code review focusing on potential improvements, bugs, inefficiencies, and odd practices:

### General Observations:
1. **Sensitive Information**: 
   - API keys and sensitive information should not be hardcoded (e.g., `TIBBER_API_KEY`, `ENTSOE_API_KEY`). Use environment variables or a secure store.

2. **Error Handling**:
   - Exception handling in the two methods `get_tibber_prices()` and `get_entsoe_prices()` logs errors but doesn't perform any recovery actions. You should implement retries or alerts on failure instead of just returning `None`.

3. **Concurrency**:
   - Several background threads (state_thread, price_thread, cop_thread) are running indefinitely. Ensure these are all nicely managed and terminated if necessary e.g., upon system shutdown.
   
4. **Global Variables**:
   - The use of many global variables can make code maintenance challenging. Encourage using classes to encapsulate data and behavior.

### Specific Code Suggestions:
1. **Logging**:
   - Ensure that logging is at an appropriate level. Sensitive data should not be logged, especially at DEBUG levels.
   - Example: API responses should be logged with caution, especially if they might contain sensitive data.

2. **HTTP and API Handling**:
   - Always check if `requests` response content is JSON before assuming it will be. You can handle `JSONDecodeError`.
   - Applying timeout with every request is essential to avoid potential hanging issues in network calls: `response = requests.post(url, data, headers, timeout=10)`

3. **Improving Code Structure**:
   - Configurations like URLs and API keys should be extracted into a configuration file or object.
   - Consider utilizing classes to better organize the code, encapsulate global state, and manage shared data aspects.

4. **Inefficient File I/O**:
   - Frequent writing to `prices.json` without batching or throttling could be a performance bottleneck.

5. **Flask Application**:
   - Make sure to run `app.run()` with debug set to False for production.
   - Proper CSRF protection should be implemented if forms are introduced.

6. **MQTT Management**:
   - Handle reconnection logic for the MQTT client; the current setup could lose connection forever without attempt to reconnect.

7. **Code Duplication**:
   - Retrieving current and historical hour price information is done in multiple locations with slightly different logic. Consider creating a helper function to centralize this logic.

8. **Error Handling in `calculate_cop`**:
   - It's good to log invalid conditions (e.g., `power <= 0`), but clarify why and what should be expected values.

9. **Using Enumerations**:
   - For states such as `energy_state_input_holding`, consider using Python's `enum` to improve code readability and avoid magic numbers.

### Logged Issue Analysis:
1. **Log Content**:
   - Make sure logs are not too verbose unless needed for debugging purposes.
   - Make sure you don't log too much sensitive information which should be sanitized or omitted.

2. **Client Command Reception**:
   - Ensure your `on_message` handler deals with commands through a secure and validated process. Check commands against a set of acceptable values or patterns to avoid malicious activity.

3. **Data Race Conditions**:
   - Double-check for potential race conditions especially in the data update routines that modify shared states like `huizen`.

### Summary:
While your code achieves the base functionality required to manage and control energy via multiple sources, there's room for significant improvements in robustness, maintainability, and security. Apply best practices regarding configuration management, error handling, and system architecting to ensure your application runs smoothly and securely.