# bn-datavisualization
Visualizations of osu! BN activity data in a webapp

Uses data from https://github.com/Naxesss/Aiess

You can scrape the Aiess discord chatlogs yourself, or download the .html (and already parsed .csv) from [here](https://sylvarus.s-ul.eu/Th9NgYhA).
Some pre-built methods are given in methods.py, and you can check app.py for how to implement your own graphs.

Requires dash, plotly, pandas, as well as beautifulsoup4 if you wish to parse the html.
