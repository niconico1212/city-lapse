### Density assumption

Source checked: Shlomo Angel, Jason Parent, Daniel L. Civco and Alejandro M. Blei, "The Persistent Decline in Urban Densities: Global and Historical Evidence of 'Sprawl'", Lincoln Institute of Land Policy Working Paper, product code WP10SA1, © 2010 (the Lincoln Institute page dates it July 2010, 151 pages). PDF: https://www.lincolninst.edu/app/uploads/2024/04/1834_1085_angel_final_1.pdf ; landing page: https://www.lincolninst.edu/publications/working-papers/persistent-decline-urban-densities/ . The full PDF was downloaded and read on 18 November 2026; page numbers below are the printed ones (PDF page = printed page + 5). Only the working paper was read, not the later journal or book versions.

What the paper says about its historical sample of 30 cities (maps and population for 1800 to 2000, density = population divided by urbanized area):

- Abstract: densities "have been in decline since their peak circa 1890±16, at an average long-term annual rate of 1.0-1.5 percent", after "an increase in average density in the nineteenth century", and average density fell threefold in the twentieth century.
- Peak (section VII, pattern 1, p. 89): the average year in which a city reached its peak density was 1890±15 (95 % confidence). Individual cities differ widely, for example Paris 1800, London 1830, Tokyo and Mexico City 1910, Shanghai 1944 (figure notes, pp. 83-88). Pattern 3 (p. 90) adds that "for simplicity's sake" 1900 can be taken as the turning point.
- Rate from each city's own peak (pattern 9, pp. 96-97): the mean of the exponential curves fitted city by city from peak density to about 2000 is 1.53±0.33 % a year; the mean 10-year rate after the peak is 1.17±0.24 % a year.
- Rate for the sample average (pattern 5, p. 91): average density fell from 285±79 to 102±29 persons per hectare between 1900 and 2000, a fitted decline of "the order of 1.0 percent per annum"; fitted to 1950-2000 only it is 1.27 % a year. Pattern 10 (p. 97): short- and long-term rates converged to about 1.0 % a year by 2000.
- Size of the decline (pattern 4, p. 90): average peak density 429±121 persons per hectare, average density in 2000 101±21, and density in 2000 was on average 31.4±8.0 % of the peak (about a threefold decline over the whole span from peak to 2000).
- Before the peak (patterns 2 and 3, p. 90): in two thirds of the cities the peak was preceded by rising density, at 0.86±0.23 % a year on average; across the whole nineteenth century the average 10-year rate of change was 0.00±0.24 % a year, not different from zero. "For dates earlier than 1800 we did not obtain any data for this study." The introduction (p. 9) mentions about 500 persons per hectare for Paris in 1800 as typical of walking cities.

Do our parameters match?

- Peak around 1890: matches (1890±15 in the text, ±16 in the abstract).
- 1.5 % a year: within what the paper reports but at the top of its range, and it is not the figure for the period we apply it to. 1.53 % is the mean decline measured from each city's own peak year; for the sample's average density from a common date the paper gives 1.0 % (1900-2000) and 1.27 % (1950-2000), and it summarises the long-term rate as "1.0-1.5 percent". Applied from 1890 to 1975, 1.5 % makes cities 3.58 times denser in 1890 than in 1975. That is as large as the paper's decline over the whole, longer span from peak to 2000 (density in 2000 averaging 31.4 % of the peak is about 3.2-fold; 429 to 101 persons per hectare is 4.2-fold) and well above the 2.8-fold fall of the sample average between 1900 and 2000. At 1.0 to 1.25 % the multiplier would be 2.3 to 2.9, and reconstructed footprints for 1890 and earlier would be 24 to 53 % larger than they are now.
- Flat before 1890: this is our assumption, not a finding of the paper. It is compatible with the nineteenth-century average (0.00±0.24 % a year), but the paper also says most cities were densifying toward their peak, and it has no data at all before 1800.

What should change: (1) the code comment and any public wording should say "1.0 to 1.5 % a year" and make clear that 1.5 % is the upper end (mean of per-city declines from each city's own peak), with the title's 'Sprawl' in quotation marks, the author "Alejandro M. Blei" and the date July 2010; (2) if the rate is meant to be a central value for a single curve starting in 1890, use about 1.25 % (multiplier 2.9) and treat 1.0 and 1.5 % as the bounds, or keep 1.5 % and state that it is the upper bound, which gives the smallest early footprints; (3) describe constant density before 1890 as an assumption of this project, unsupported by this source before 1800.

### Atlas of Urban Expansion

Source: Atlas of Urban Expansion, 2016 edition, "Areas and Densities Table 1" downloaded on 18 November 2026 from the Data page, http://www.atlasofurbanexpansion.org/data (file http://atlasofurbanexpansion.org/file-manager/userfiles/data_page/Areas_and_Densities_Tables/Areas_and_Densities_Table_1.csv ; 200 cities, three dates each). The Dhaka and Guangzhou figures were also checked against the city pages (for example http://www.atlasofurbanexpansion.org/cities/view/Dhaka ). The table gives two measures for each date. "Built-up area" is impervious surface classified from 30 m Landsat pixels; "urban extent" is the built-up area plus the urbanized open space around and inside it (open space within 100 m of built-up pixels and enclosed open space under 200 hectares). The table below uses the urban extent, converted from hectares, as the main comparison, and gives the built-up area in the last two columns. Our value is the built-up footprint in `data/footprints/<slug>/summary.json` (100 m cells with at least 5 % built surface inside the GHSL urban centre), read at 07:58 UTC on 18 November 2026, at the five-year epoch nearest to the Atlas image date.

The Atlas covers 38 of our 50 cities; it has no entry for Bandung, Bengaluru, Chennai, Dar es Salaam, Delhi, Hajipur, Jakarta, Kuala Lumpur, Lima, Nagoya, Rio de Janeiro or Suzhou.

| City | Atlas year | Atlas area km2 | Atlas measure | Our year | Our area km2 | Ratio ours/Atlas | Atlas built-up km2 | Ratio ours/built-up |
|---|---|---|---|---|---|---|---|---|
| Ahmedabad | 1989 | 171.9 | urban extent | 1990 | 202.8 | 1.18 | 121.7 | 1.67 |
| Ahmedabad | 2000 | 212.9 | urban extent | 2000 | 241.6 | 1.13 | 159.2 | 1.52 |
| Ahmedabad | 2013 | 274.1 | urban extent | 2015 | 288.3 | 1.05 | 211.0 | 1.37 |
| Alexandria | 1987 | 99.9 | urban extent | 1990 | 156.5 | 1.57 | 78.2 | 2.00 |
| Alexandria | 1999 | 203.6 | urban extent | 2000 | 174.7 | 0.86 | 155.1 | 1.13 |
| Alexandria | 2013 | 304.2 | urban extent | 2015 | 213.4 | 0.70 | 227.8 | 0.94 |
| Bangkok | 1988 | 969.2 | urban extent | 1990 | 1,026.2 | 1.06 | 507.5 | 2.02 |
| Bangkok | 2002 | 1,570.2 | urban extent | 2000 | 1,565.7 | 1.00 | 900.9 | 1.74 |
| Bangkok | 2015 | 2,944.6 | urban extent | 2015 | 2,007.5 | 0.68 | 1,729.1 | 1.16 |
| Beijing | 1988 | 987.3 | urban extent | 1990 | 923.8 | 0.94 | 667.6 | 1.38 |
| Beijing | 1999 | 1,755.2 | urban extent | 2000 | 1,214.1 | 0.69 | 1,142.3 | 1.06 |
| Beijing | 2013 | 4,556.8 | urban extent | 2015 | 1,582.9 | 0.35 | 2,654.3 | 0.60 |
| Bogotá | 1989 | 321.2 | urban extent | 1990 | 342.1 | 1.06 | 245.8 | 1.39 |
| Bogotá | 2001 | 366.4 | urban extent | 2000 | 364.6 | 1.00 | 285.0 | 1.28 |
| Bogotá | 2010 | 397.2 | urban extent | 2010 | 383.1 | 0.96 | 318.9 | 1.20 |
| Buenos Aires | 1989 | 1,330.1 | urban extent | 1990 | 1,534.2 | 1.15 | 990.1 | 1.55 |
| Buenos Aires | 2001 | 1,536.3 | urban extent | 2000 | 1,674.1 | 1.09 | 1,156.4 | 1.45 |
| Buenos Aires | 2014 | 1,933.9 | urban extent | 2015 | 1,778.7 | 0.92 | 1,473.1 | 1.21 |
| Cairo | 1992 | 412.0 | urban extent | 1995 | 775.8 | 1.88 | 297.2 | 2.61 |
| Cairo | 2003 | 581.7 | urban extent | 2005 | 926.4 | 1.59 | 455.1 | 2.04 |
| Cairo | 2013 | 1,364.0 | urban extent | 2015 | 1,019.8 | 0.75 | 930.9 | 1.10 |
| Dhaka | 1989 | 138.8 | urban extent | 1990 | 1,148.5 | 8.28 | 74.7 | 15.37 |
| Dhaka | 1999 | 228.2 | urban extent | 2000 | 1,320.1 | 5.78 | 124.8 | 10.58 |
| Dhaka | 2014 | 365.4 | urban extent | 2015 | 1,667.0 | 4.56 | 246.8 | 6.76 |
| Guangzhou | 1991 | 150.2 | urban extent | 1990 | 1,133.6 | 7.55 | 81.8 | 13.85 |
| Guangzhou | 2000 | 1,954.7 | urban extent | 2000 | 2,437.5 | 1.25 | 1,201.8 | 2.03 |
| Guangzhou | 2014 | 5,082.6 | urban extent | 2015 | 3,220.1 | 0.63 | 3,231.5 | 1.00 |
| Hangzhou | 1990 | 99.2 | urban extent | 1990 | 350.7 | 3.53 | 46.3 | 7.58 |
| Hangzhou | 2000 | 855.5 | urban extent | 2000 | 647.2 | 0.76 | 437.0 | 1.48 |
| Hangzhou | 2013 | 3,721.9 | urban extent | 2015 | 1,041.8 | 0.28 | 1,962.6 | 0.53 |
| Ho Chi Minh City | 1989 | 84.3 | urban extent | 1990 | 528.4 | 6.27 | 54.5 | 9.69 |
| Ho Chi Minh City | 1999 | 220.2 | urban extent | 2000 | 802.4 | 3.64 | 150.6 | 5.33 |
| Ho Chi Minh City | 2015 | 993.9 | urban extent | 2015 | 1,018.1 | 1.02 | 634.8 | 1.60 |
| Hyderabad | 1990 | 216.7 | urban extent | 1990 | 321.2 | 1.48 | 126.7 | 2.54 |
| Hyderabad | 1999 | 419.6 | urban extent | 2000 | 454.5 | 1.08 | 266.7 | 1.70 |
| Hyderabad | 2014 | 730.0 | urban extent | 2015 | 611.1 | 0.84 | 461.7 | 1.32 |
| Istanbul | 1990 | 469.3 | urban extent | 1990 | 632.9 | 1.35 | 283.7 | 2.23 |
| Istanbul | 2002 | 871.3 | urban extent | 2000 | 751.4 | 0.86 | 577.6 | 1.30 |
| Istanbul | 2013 | 1,316.1 | urban extent | 2015 | 823.1 | 0.63 | 1,025.9 | 0.80 |
| Johannesburg | 1990 | 1,408.0 | urban extent | 1990 | 1,102.6 | 0.78 | 763.3 | 1.44 |
| Johannesburg | 1998 | 1,641.0 | urban extent | 2000 | 1,213.2 | 0.74 | 928.3 | 1.31 |
| Johannesburg | 2013 | 2,625.7 | urban extent | 2015 | 1,270.7 | 0.48 | 1,811.9 | 0.70 |
| Karachi | 1991 | 223.3 | urban extent | 1990 | 429.7 | 1.92 | 180.6 | 2.38 |
| Karachi | 2000 | 341.3 | urban extent | 2000 | 484.2 | 1.42 | 275.4 | 1.76 |
| Karachi | 2013 | 453.3 | urban extent | 2015 | 530.9 | 1.17 | 350.2 | 1.52 |
| Kinshasa | 1994 | 146.4 | urban extent | 1995 | 346.1 | 2.36 | 78.8 | 4.39 |
| Kinshasa | 2000 | 292.1 | urban extent | 2000 | 348.8 | 1.19 | 201.4 | 1.73 |
| Kinshasa | 2013 | 456.8 | urban extent | 2015 | 377.7 | 0.83 | 337.6 | 1.12 |
| Kolkata | 1990 | 313.2 | urban extent | 1990 | 796.9 | 2.54 | 180.5 | 4.42 |
| Kolkata | 2003 | 596.0 | urban extent | 2005 | 1,035.5 | 1.74 | 335.8 | 3.08 |
| Kolkata | 2014 | 968.7 | urban extent | 2015 | 1,133.3 | 1.17 | 602.8 | 1.88 |
| Lagos | 1984 | 297.4 | urban extent | 1985 | 616.5 | 2.07 | 194.0 | 3.18 |
| Lagos | 2000 | 580.6 | urban extent | 2000 | 695.8 | 1.20 | 380.8 | 1.83 |
| Lagos | 2013 | 826.8 | urban extent | 2015 | 939.8 | 1.14 | 527.9 | 1.78 |
| Lahore | 1991 | 177.5 | urban extent | 1990 | 360.2 | 2.03 | 115.2 | 3.13 |
| Lahore | 2000 | 231.6 | urban extent | 2000 | 434.8 | 1.88 | 149.6 | 2.91 |
| Lahore | 2013 | 371.4 | urban extent | 2015 | 533.7 | 1.44 | 247.8 | 2.15 |
| London | 1989 | 1,973.5 | urban extent | 1990 | 1,187.6 | 0.60 | 1,315.0 | 0.90 |
| London | 2000 | 2,429.5 | urban extent | 2000 | 1,215.7 | 0.50 | 1,673.7 | 0.73 |
| London | 2013 | 2,507.7 | urban extent | 2015 | 1,241.3 | 0.49 | 1,772.7 | 0.70 |
| Los Angeles | 1990 | 4,882.6 | urban extent | 1990 | 3,568.8 | 0.73 | 3,539.4 | 1.01 |
| Los Angeles | 2000 | 5,517.0 | urban extent | 2000 | 3,765.3 | 0.68 | 4,177.3 | 0.90 |
| Los Angeles | 2014 | 5,859.0 | urban extent | 2015 | 3,895.7 | 0.66 | 4,590.5 | 0.85 |
| Luanda | 1991 | 140.4 | urban extent | 1990 | 578.5 | 4.12 | 104.1 | 5.56 |
| Luanda | 2000 | 231.8 | urban extent | 2000 | 644.0 | 2.78 | 171.8 | 3.75 |
| Luanda | 2014 | 509.7 | urban extent | 2015 | 701.5 | 1.38 | 368.9 | 1.90 |
| Manila | 1990 | 579.9 | urban extent | 1990 | 1,080.3 | 1.86 | 356.7 | 3.03 |
| Manila | 2000 | 834.2 | urban extent | 2000 | 1,187.7 | 1.42 | 563.0 | 2.11 |
| Manila | 2014 | 1,104.1 | urban extent | 2015 | 1,308.8 | 1.19 | 703.3 | 1.86 |
| Mexico City | 1990 | 1,034.6 | urban extent | 1990 | 1,452.1 | 1.40 | 709.5 | 2.05 |
| Mexico City | 2000 | 1,364.8 | urban extent | 2000 | 1,518.4 | 1.11 | 991.1 | 1.53 |
| Mexico City | 2014 | 2,100.2 | urban extent | 2015 | 1,625.3 | 0.77 | 1,618.2 | 1.00 |
| Moscow | 1991 | 1,762.7 | urban extent | 1990 | 906.4 | 0.51 | 1,089.1 | 0.83 |
| Moscow | 2001 | 2,475.7 | urban extent | 2000 | 1,007.7 | 0.41 | 1,600.2 | 0.63 |
| Moscow | 2014 | 3,576.0 | urban extent | 2015 | 1,072.0 | 0.30 | 2,234.4 | 0.48 |
| Mumbai | 1991 | 366.8 | urban extent | 1990 | 335.9 | 0.92 | 278.1 | 1.21 |
| Mumbai | 2001 | 430.0 | urban extent | 2000 | 393.2 | 0.91 | 334.2 | 1.18 |
| Mumbai | 2014 | 705.3 | urban extent | 2015 | 422.2 | 0.60 | 531.4 | 0.79 |
| New York | 1991 | 6,888.8 | urban extent | 1990 | 2,168.6 | 0.31 | 5,092.4 | 0.43 |
| New York | 2000 | 9,227.2 | urban extent | 2000 | 2,256.2 | 0.24 | 7,208.6 | 0.31 |
| New York | 2011 | 9,511.0 | urban extent | 2010 | 2,311.8 | 0.24 | 7,478.5 | 0.31 |
| Osaka | 1989 | 954.3 | urban extent | 1990 | 1,620.5 | 1.70 | 720.2 | 2.25 |
| Osaka | 2001 | 1,077.6 | urban extent | 2000 | 1,686.2 | 1.56 | 879.0 | 1.92 |
| Osaka | 2014 | 1,137.6 | urban extent | 2015 | 1,736.7 | 1.53 | 950.8 | 1.83 |
| Paris | 1987 | 1,972.1 | urban extent | 1985 | 1,036.0 | 0.53 | 1,277.9 | 0.81 |
| Paris | 2000 | 2,313.6 | urban extent | 2000 | 1,087.8 | 0.47 | 1,586.3 | 0.69 |
| Paris | 2014 | 2,778.5 | urban extent | 2015 | 1,110.7 | 0.40 | 1,986.3 | 0.56 |
| São Paulo | 1988 | 1,555.3 | urban extent | 1990 | 1,425.4 | 0.92 | 1,138.7 | 1.25 |
| São Paulo | 2000 | 1,949.9 | urban extent | 2000 | 1,550.4 | 0.80 | 1,564.0 | 0.99 |
| São Paulo | 2014 | 2,119.1 | urban extent | 2015 | 1,627.4 | 0.77 | 1,724.3 | 0.94 |
| Seoul | 1991 | 958.0 | urban extent | 1990 | 973.6 | 1.02 | 675.7 | 1.44 |
| Seoul | 2000 | 1,817.5 | urban extent | 2000 | 1,225.6 | 0.67 | 1,164.2 | 1.05 |
| Seoul | 2014 | 3,147.5 | urban extent | 2015 | 1,442.5 | 0.46 | 1,995.8 | 0.72 |
| Shanghai | 1991 | 1,955.8 | urban extent | 1990 | 978.9 | 0.50 | 950.7 | 1.03 |
| Shanghai | 2000 | 3,675.6 | urban extent | 2000 | 1,541.9 | 0.42 | 2,009.8 | 0.77 |
| Shanghai | 2015 | 4,688.7 | urban extent | 2015 | 2,251.0 | 0.48 | 3,200.5 | 0.70 |
| Shenzhen | 1987 | 138.0 | urban extent | 1990 | 327.7 | 2.37 | 100.2 | 3.27 |
| Shenzhen | 2000 | 600.9 | urban extent | 2000 | 789.5 | 1.31 | 419.4 | 1.88 |
| Shenzhen | 2013 | 1,041.2 | urban extent | 2015 | 966.5 | 0.93 | 785.2 | 1.23 |
| Taipei | 1990 | 301.2 | urban extent | 1990 | 483.8 | 1.61 | 218.5 | 2.21 |
| Taipei | 2001 | 607.8 | urban extent | 2000 | 557.0 | 0.92 | 380.4 | 1.46 |
| Taipei | 2014 | 1,105.3 | urban extent | 2015 | 617.8 | 0.56 | 702.4 | 0.88 |
| Tehran | 1991 | 471.0 | urban extent | 1990 | 544.7 | 1.16 | 321.5 | 1.69 |
| Tehran | 2000 | 620.0 | urban extent | 2000 | 583.3 | 0.94 | 474.3 | 1.23 |
| Tehran | 2010 | 784.0 | urban extent | 2010 | 614.8 | 0.78 | 613.7 | 1.00 |
| Tianjin | 1990 | 272.4 | urban extent | 1990 | 286.1 | 1.05 | 201.2 | 1.42 |
| Tianjin | 2000 | 383.6 | urban extent | 2000 | 360.7 | 0.94 | 273.3 | 1.32 |
| Tianjin | 2013 | 2,362.9 | urban extent | 2015 | 507.3 | 0.21 | 1,524.4 | 0.33 |
| Tokyo | 1990 | 4,179.0 | urban extent | 1990 | 3,768.6 | 0.90 | 2,786.9 | 1.35 |
| Tokyo | 2000 | 4,638.9 | urban extent | 2000 | 3,969.3 | 0.86 | 3,248.3 | 1.22 |
| Tokyo | 2014 | 6,432.4 | urban extent | 2015 | 4,130.3 | 0.64 | 4,489.3 | 0.92 |
| Wuhan | 1990 | 303.5 | urban extent | 1990 | 283.3 | 0.93 | 174.6 | 1.62 |
| Wuhan | 2000 | 442.7 | urban extent | 2000 | 372.7 | 0.84 | 289.2 | 1.29 |
| Wuhan | 2013 | 1,837.2 | urban extent | 2015 | 512.9 | 0.28 | 1,028.3 | 0.50 |

What the comparison shows. Across the 114 city-dates the ratio of our area to the Atlas urban extent runs from 0.21 (Tianjin 2013) to 8.28 (Dhaka 1989) with a median of 0.94, and 84 of the 114 are within a factor of two. The agreement drifts with time in every one of the 38 cities: the median ratio is 1.26 at the first Atlas date, 0.97 at the second and 0.72 at the third (2.01, 1.46 and 1.00 against the Atlas built-up area), because our footprints grow by a median factor of 1.29 between the first and third dates while the Atlas urban extents grow by 2.52. The largest disagreements are Dhaka at all three dates (4.6 to 8.3), Ho Chi Minh City 1989 (6.3), Guangzhou 1991 (7.5), Luanda 1991 (4.1) and Hangzhou 1990 (3.5) on the high side, and Tianjin 2013 (0.21), New York (0.24 to 0.31), Wuhan 2013 (0.28), Hangzhou 2013 (0.28), Moscow 2014 (0.30) and Beijing 2013 (0.35) on the low side.

Limits. The two sources do not measure the same thing or the same territory, so a ratio between 0.5 and 2 is not evidence of an error either way. Our footprint is confined to one fixed GHSL urban-centre polygon per city: for 17 of the 38 cities the latest Atlas urban extent is larger than that whole polygon (New York 9,511 km2 against a 3,031 km2 polygon, Tianjin 2,363 against 671), so those ratios cannot approach 1, while for Dhaka the polygon (6,611 km2) takes in a wide densely settled region that the Atlas does not count as the city, and Guangzhou and Shenzhen share one polygon that we split. The systematic slower growth in our series is the finding most worth a second look; this check did not establish its cause. Candidates are the fixed polygon, the 5 % threshold (a sparsely built cell already counts in full, so later infill adds no area) and differences between the GHSL and Atlas classifications in the early epochs. Some early Atlas values also look inconsistent with their own later dates (Guangzhou 150 km2 in 1991 and 1,955 km2 in 2000; Hangzhou 99 km2 in 1990 and 856 km2 in 2000), so the worst first-date ratios should not be read as errors in our data alone.
