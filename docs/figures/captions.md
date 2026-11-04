# Blog figures

Generated from the Databricks gold tables by `scripts/build_figures.py`. Suggested order and captions:

**Figure 1.** Popularity against the number of major allergens each candy's label lists, for the 59 candies with at
least two labeled products. Candies with none of the six average a 45% win rate; candies with five or more average 66%.
`fig1_allergens_vs_popularity.png`

**Figure 2.** Share of the unrestricted bowl's popularity that each allergy-safe bowl keeps. A peanut-free bowl keeps
78.0%, and a bowl free of all six allergens keeps 68.7%. `fig2_popularity_retained.png`

**Figure 3.** Chocolate and non-chocolate candies in each 10-candy bowl. The milk-free and free-of-all-six bowls contain
no chocolate at all. `fig3_chocolate_share.png`

**Figure 4.** Median sugar per 100 g in each bowl. Allergy-safe bowls rely on fruit candy and contain more sugar.
`fig4_sugar_by_bowl.png`

**Figure 5.** Allergen status of the 20 most popular candies, from matched Open Food Facts labels. Hatched cells have
no matched ingredient list. `fig5_allergen_heatmap.png`

**Figure 6.** Name-only matching compared with the curated rules. Matching on the name alone links 53 candies but also
80 products that are not candy; the curated rules link 68 candies with no false matches.
`fig6_matching_methods.png`

**Figure 7.** Each candy's 2017 allergen status compared with products edited since the daily change feed started. 12
of the 19 candies with enough current data changed. `fig7_label_changes.png`
