from src import analyze_cleaned_data_from_csv

# Analyze a saved CSV file containing line detection points
stats_result = analyze_cleaned_data_from_csv("lines.csv")

print(f"Total Cleaned Lines: {stats_result['total_lines']}")
print(f"Detected Pixel Indexes: {stats_result['pixel_indexes']}")

if stats_result['stats']:
    print("\nStatistics:")
    print(f"  Mean difference: {stats_result['stats']['mean_diff']:.2f} px")
    print(f"  Standard deviation: {stats_result['stats']['std_diff']:.2f} px")
    print(f"  Min difference: {stats_result['stats']['min_diff']} px")
    print(f"  Max difference: {stats_result['stats']['max_diff']} px")