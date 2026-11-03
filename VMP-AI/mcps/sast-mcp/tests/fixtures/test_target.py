def process_data(user_input):
    # This is a known vulnerability that Bandit will flag (B307: eval)
    result = eval(user_input)
    return result

def main():
    print("Test file")

if __name__ == "__main__":
    main()
