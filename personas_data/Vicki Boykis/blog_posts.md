# Blog Posts

## [My favorite use-case for AI is writing logs](https://vickiboykis.com/2025/07/16/my-favorite-use-case-for-ai-is-writing-logs/)

Jul 16 2025

One of my favorite AI dev products today is Full Line Code Completion in PyCharm (bundled with the IDE since late 2023). It’s extremely well-thought out, unintrusive, and makes me a more effective developer. Most importantly, it still keeps me mostly in control of my code. I’ve now used it in GoLand as well. I’ve been a happy JetBrains customer for a long time now, and it’s because they ship features like this.

I frequently work with code that involves sequential data processing, computations, and async API calls across multiple services. I also deal with a lot of precise vector operations in PyTorch that shape suffixes don’t always illuminate. So, print statement debugging and writing good logs has been a critical part of my workflows for years.

As Kerningan and Pike say in The Practice of Programming about preferring print to debugging,

…[W]e find stepping through a program less productive than thinking harder and adding output statements and self-checking code at critical places. Clicking over statements takes longer than scanning the output of judiciously-placed displays. It takes less time to decide where to put print statements than to single-step to the critical section of code, even assuming we know where that is.

One thing that is annoying about logging is that f-strings are great but become repetitive to write if you have to write them over and over, particularly if you’re formatting values or accessing elements of data frames, lists, and nested structures, and particularly if you have to scan your codebase to find those variables. Writing good logs is important but also breaks up a debugging flow.

The amount of cognitive overhead in this deceptively simple log is several levels deep: you have to first stop to type logger.info (or is it logging.info? I use both loguru and logger depending on the codebase and end up always getting the two confused.) Then, the parentheses, the f-string itself, and then the variables in brackets. Now, was it your_variable or your_variable_with_edits from five lines up? And what’s the syntax for accessing a subset of df.head again?

With full-line-code completion, JetBrains’ model auto-infers the log completion from the surrounding text, with a limit of 384 characters. Inference starts by taking the file extension as input, combined with the filepath, and then the part of the code above the input cursor, so that all of the tokens in the file extension, plus path, plus code above the caret, fit. Everything is combined and sent to the model in the prompt.

The constrained output good enough most of the time that it speeds up my workflow a lot. An added bonus is that it often writes a much clearer log than I, a lazy human, would write, logs. Because they’re so concise, I often don’t even remove when I’m done debugging because they’re now valuable in prod.

Here’s an example from a side project I’m working on. In the first case, the is autocomplete inferring that I actually want to check the Redis URL, a logical conclusion here.

In this second case, it assumes I’d like the shape of the dataframe, also a logical conclusion because the profiling dataframes is a very popular use-case for logs.

Implementation

The coolest part of this feature is that the inference model is entirely local to your machine.

This enforces a few very important requirements on the development team, namely compression and speed.

This is drastically different from the current assumptions around how we build and ship LLMs: that they need to be extremely large, general-purpose models served over proprietary APIs. we We find ourselves in a very constrained solution space because we no longer have to do all this other stuff that generalized LLMs have to do: write poetry, reason through math problems, act as OCR, offer code canvas templating, write marketing emails, and generate Studio Ghibli memes.

All we have to do is train a model to complete a single line of code with a context of 384 characters! And then compress the crap out of that model so that it can fit on-device and perform inference.

So how did they do it? Luckily, JetBrains published a paper on this, and there are a bunch of interesting notes. The work is split into two parts, model training, and then the integration of the plugin itself.

The model is trained is done in PyTorch and then quantized.

Because they were able to so clearly focus on the domain and understanding of how code inference works, focus on a single programming languages with its own nuances, they were able to make the training data set smaller, make the output more exact, and spend much less time and money training the model.

The actual plugin that’s included in PyCharm “is implemented in Kotlin, however, it utilizes an additional native server that is run locally and is implemented in C++” for serving the inference tokens.

In order to prepare the model for serving, they:

Quantized it from FP32 to INT8 which compressed the model from 400 MB to 100 MB

Prepared as a served ONNX RT artifact, which allowed them to use CPU inference, which removed the CUDA overhead tax(later, they switched to using llama.cpp to serve the llama model architecture for the server.

Finally, in order to perform inference on a sequence of tokens, they use beam search. Generally, Transformer-decoders are trained on predicting the next token in any given sequence so any individual step will give you a list of tokens along with their ranked probabilities (cementing my long-running theory that everything is a search problem).

Since this is computationally impossible at large numbers of tokens, a number of solutions exist to solve the problem of decoding optimally. Beam search creates a graph of all possible returned token sequences and expands at each node with the highest potential probability, limiting to k possible beams. In FLCC, the max number of beams, k, is 20, and they chose to limit generation to collect only those hypotheses that end with a newline character.

Additionally they made use of a number of caching strategies, including initializing the model at 50% of total context - i.e. it starts by preloading ~192 characters of previous code, to give you space to either go back and edit old code, which now no longer has to be put into context, or to add new code, which is then added to the context. That way, if your cursor clicks on code you’ve already written, the model doesn’t need to re-infer.

There are a number of other very cool architecture and model decisions from the paper that are very worth reading and that show the level of care put into the input data, the modeling, and the inference architecture.

The bottom line is that, for me as a user, this experience is extremely thoughtful. It has saved me countless times both in print log debugging and in the logs I ship to prod.

In LLM land, there’s both a place for large, generalist models, and there’s a place for small models, and while much of the rest of the world writes about the former, I’m excited to also find more applications built with the latter.

#llms #machine learning #compression #tokenization #training #python #engineering #local models

---

## [Writing for distributed teams](https://vickiboykis.com/2021/07/17/writing-for-distributed-teams/)

Jul 17 2021

This week was my first anniversary since I started at Automattic in the spring of 2020, and I was going through my work artifacts to reflect on what I’ve done so far this year. One thing that completely surprised me was that it turns out that I only sent 11 emails this entire year.

How is it possible? The answer is P2s.

For those not familiar with Automattic, the company behind WordPress.com and Tumblr, which I now work on as a machine learning engineer, one of the big MOs of the company is that we communicate as much as possible in durable written format since we’re distributed.

How does no email square with complete distributed communication? The answer is P2. P2 is the name of a WordPress theme that every team at Automattic uses internally for documentation. Essentially, we have (probably) hundreds of P2s, for current teams, for teams that used to exist, for special interest groups, and events.

When you “P2” something, you’re writing a blog post, where you can tag in coworkers and cross-post to other P2s. What do teams use P2s for? Absolutely everything. Checklists for onboarding, status reports on projects, thoughts about detailing projects, discussions about best coding practices, architectural diagrams, marketing data analyses, and more. The best part is that the entire company’s history of P2s is available to search through. Also, you can subscribe to literally any P2, and comment on it as necessary, starting with your own team’s.

Why P2s? Because they capture fleeting one-off written communication: you can read a P2 at your own speed, in your own timezone, which is key since we operate across all timezones.

Here’s Matt with more on it:

P2 is the evolution of the blog for the purpose of working within and across teams. It’s organized much like a Yammer or Facebook stream, but on the back end it still operates like a blog, allowing for archiving, advanced search, and rich media embeds.

Here’s a great post on the company MO and more detail:

Most of our company communication is done on what we call “p2s”. You can actually create your own here. Think of them as free flowing, chronological sites where people can share updates, tag others for feedback, cross post to other p2s, and more. I’m on the more talkative and connected side of things which is reflected in the stats you see below (almost at the 1.5 million word mark!):

Conversations on P2s take place in line, update in real time, and provide space for threaded replies. We’ve stuck with P2 for years now, and it has ultimately evolved into a rich source of institutional wisdom and collective company memory.

If you want to know what the team worked on last week, it’s in a P2. If you want to look for the results of a meeting from last year, you can do a keyword search.

A saying around the company is that you should “P2 something or it didn’t happen”, aka it doesn’t get surfaced to a place where everyone can read about it, lost languishing in an email thread.

This is a completely different paradigm than I’ve ever worked in, which has been a world usually riddled with information lost to Slack, Confluence, and dozens of email re:re:res.

It’s true that I still spend an enormous amount of time in Slack, but the company’s focus on P2 as THE place where institutional memory lives, and where other people can interact with your work, means that there is an internal incentive to get stuff out of Slack and into P2s, where they can live forever and be collected with other P2s to form a cohesive view of how a team, project, or division operates over time. In this way, the company also owns its own institutional knoweldge instead of having it locked away in third-party tools.

The nature of reading P2s means even if you only write one or two P2s a month, you can send them around in meetings or Slack conversations as solid anchors and points of reference. (Another note is that we definitely do still have meetings, and I spend a good deal of my day in Slack, but I don’t come away from these times feeling like the information is lost, because I’m always building towards a P2 on whatever was discussed in either format.)

I’m super biased on this, but as someone who spends a lot of time processing things in writing, and who enjoys writing, I love P2s. I love that they make me clearly state what was jumbled in my head, I love that I now have a concrete trail, with links, of things that I’ve worked on. I love that I essentially am encouraged to blog internally, about things that I’ve worked on, my thoughts on projects, my progress, and ideas I have, and that I can do it mostly at a pace that works for my own work schedule.

Of course, as with any technology, P2s come with their own tradeoffs: it can be easy to get lost reading through hundreds of P2 posts every day and responding unless you have a very good P2 strategy and focus on the ones relevant to you. It can be hard to synthesize a lot of technical information into a post that’s relevant enough to both engineers and business people and offer enough context and value to continue the conversation. It can be hard to go back far enough to find all of the historical context you need for your own P2s.

But, in spite of these issues, I really love the P2 as a medium for institutional knowledge and will definitely take the idea of P2s wherever I am in my career from now on.

#collaboration #writing #engineering culture #distributed systems #career advice

---

