def get_user_choice(prompt, valid_choices):
    """Gets a valid user choice."""
    choice = input(prompt)
    while choice not in valid_choices:
        print("❌ Invalid choice. Please try again.")
        choice = input(prompt)
    return choice