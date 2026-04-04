# Blog Posts

## [Home - colah's blog](https://colah.github.io/)

Writing rough notes allows me share more content, since polishing takes lots of time. While I hope it's useful, it's likely lower quality and less carefully considered than my usual articles.

Sometimes I write twitter threads as a low-effort way to express something I'd have written an essay about if I had more time.

---

## [Neural Networks, Manifolds, and Topology](https://colah.github.io/posts/2014-03-NN-Manifolds-Topology/)

Posted on April 6, 2014

Recently, there’s been a great deal of excitement and interest in deep neural networks because they’ve achieved breakthrough results in areas such as computer vision.1

However, there remain a number of concerns about them. One is that it can be quite challenging to understand what a neural network is really doing. If one trains it well, it achieves high quality results, but it is challenging to understand how it is doing so. If the network fails, it is hard to understand what went wrong.

While it is challenging to understand the behavior of deep neural networks in general, it turns out to be much easier to explore low-dimensional deep neural networks – networks that only have a few neurons in each layer. In fact, we can create visualizations to completely understand the behavior and training of such networks. This perspective will allow us to gain deeper intuition about the behavior of neural networks and observe a connection linking neural networks to an area of mathematics called topology.

A number of interesting things follow from this, including fundamental lower-bounds on the complexity of a neural network capable of classifying certain datasets.

Let’s begin with a very simple dataset, two curves on a plane. The network will learn to classify points as belonging to one or the other.

The obvious way to visualize the behavior of a neural network – or any classification algorithm, for that matter – is to simply look at how it classifies every possible data point.

We’ll start with the simplest possible class of neural network, one with only an input layer and an output layer. Such a network simply tries to separate the two classes of data by dividing them with a line.

That sort of network isn’t very interesting. Modern neural networks generally have multiple layers between their input and output, called “hidden” layers. At the very least, they have one.

As before, we can visualize the behavior of this network by looking at what it does to different points in its domain. It separates the data with a more complicated curve than a line.

With each layer, the network transforms the data, creating a new representation.2 We can look at the data in each of these representations and how the network classifies them. When we get to the final representation, the network will just draw a line through the data (or, in higher dimensions, a hyperplane).

In the previous visualization, we looked at the data in its “raw” representation. You can think of that as us looking at the input layer. Now we will look at it after it is transformed by the first layer. You can think of this as us looking at the hidden layer.

Each dimension corresponds to the firing of a neuron in the layer.

In the approach outlined in the previous section, we learn to understand networks by looking at the representation corresponding to each layer. This gives us a discrete list of representations.

The tricky part is in understanding how we go from one to another. Thankfully, neural network layers have nice properties that make this very easy.

There are a variety of different kinds of layers used in neural networks. We will talk about tanh layers for a concrete example. A tanh layer \(\tanh(Wx+b)\) consists of:

We can visualize this as a continuous transformation, as follows:

The story is much the same for other standard layers, consisting of an affine transformation followed by pointwise application of a monotone activation function.

We can apply this technique to understand more complicated networks. For example, the following network classifies two spirals that are slightly entangled, using four hidden layers. Over time, we can see it shift from the “raw” representation to higher level ones it has learned in order to classify the data. While the spirals are originally entangled, by the end they are linearly separable.

On the other hand, the following network, also using multiple layers, fails to classify two spirals that are more entangled.

---

## [Deep Learning, NLP, and Representations](https://colah.github.io/posts/2014-07-NLP-RNNs-Representations/)

Posted on July 7, 2014

neural networks, deep learning, representations, NLP, recursive neural networks

In the last few years, deep neural networks have dominated pattern recognition. They blew the previous state of the art out of the water for many computer vision tasks. Voice recognition is also moving that way.

But despite the results, we have to wonder… why do they work so well?

This post reviews some extremely remarkable results in applying deep neural networks to natural language processing (NLP). In doing so, I hope to make accessible one promising answer as to why deep neural networks work. I think it’s a very elegant perspective.

A neural network with a hidden layer has universality: given enough hidden units, it can approximate any function. This is a frequently quoted – and even more frequently, misunderstood and applied – theorem.

It’s true, essentially, because the hidden layer can be used as a lookup table.

For simplicity, let’s consider a perceptron network. A perceptron is a very simple neuron that fires if it exceeds a certain threshold and doesn’t fire if it doesn’t reach that threshold. A perceptron network gets binary (0 and 1) inputs and gives binary outputs.

Note that there are only a finite number of possible inputs. For each possible input, we can construct a neuron in the hidden layer that fires for that input,1 and only on that specific input. Then we can use the connections between that neuron and the output neurons to control the output in that specific case. 2

And so, it’s true that one hidden layer neural networks are universal. But there isn’t anything particularly impressive or exciting about that. Saying that your model can do the same thing as a lookup table isn’t a very strong argument for it. It just means it isn’t impossible for your model to do the task.

Universality means that a network can fit to any training data you give it. It doesn’t mean that it will interpolate to new data points in a reasonable way.

No, universality isn’t an explanation for why neural networks work so well. The real reason seems to be something much more subtle… And, to understand it, we’ll first need to understand some concrete results.

I’d like to start by tracing a particularly interesting strand of deep learning research: word embeddings. In my personal opinion, word embeddings are one of the most exciting area of research in deep learning at the moment, although they were originally introduced by Bengio, et al. more than a decade ago.3 Beyond that, I think they are one of the best places to gain intuition about why deep learning is so effective.

A word embedding \(W: \mathrm{words} \to \mathbb{R}^n\) is a paramaterized function mapping words in some language to high-dimensional vectors (perhaps 200 to 500 dimensions). For example, we might find:

\[W(``\text{cat}\!") = (0.2,~ \text{-}0.4,~ 0.7,~ ...)\]

\[W(``\text{mat}\!") = (0.0,~ 0.6,~ \text{-}0.1,~ ...)\]

(Typically, the function is a lookup table, parameterized by a matrix, \(\theta\), with a row for each word: \(W_\theta(w_n) = \theta_n\).)

\(W\) is initialized to have random vectors for each word. It learns to have meaningful vectors in order to perform some task.

For example, one task we might train a network for is predicting whether a 5-gram (sequence of five words) is ‘valid.’ We can easily get lots of 5-grams from Wikipedia (eg. “cat sat on the mat”) and then ‘break’ half of them by switching a word with a random word (eg. “cat sat song the mat”), since that will almost certainly make our 5-gram nonsensical.

The model we train will run each word in the 5-gram through \(W\) to get a vector representing it and feed those into another ‘module’ called \(R\) which tries to predict if the 5-gram is ‘valid’ or ‘broken.’ Then, we’d like:

---

## [Calculus on Computational Graphs: Backpropagation](https://colah.github.io/posts/2015-08-Backprop/)

Posted on August 31, 2015

Backpropagation is the key algorithm that makes training deep models computationally tractable. For modern neural networks, it can make training with gradient descent as much as ten million times faster, relative to a naive implementation. That’s the difference between a model taking a week to train and taking 200,000 years.

Beyond its use in deep learning, backpropagation is a powerful computational tool in many other areas, ranging from weather forecasting to analyzing numerical stability – it just goes by different names. In fact, the algorithm has been reinvented at least dozens of times in different fields (see Griewank (2010)). The general, application independent, name is “reverse-mode differentiation.”

Fundamentally, it’s a technique for calculating derivatives quickly. And it’s an essential trick to have in your bag, not only in deep learning, but in a wide variety of numerical computing situations.

Computational graphs are a nice way to think about mathematical expressions. For example, consider the expression \(e=(a+b)*(b+1)\). There are three operations: two additions and one multiplication. To help us talk about this, let’s introduce two intermediary variables, \(c\) and \(d\) so that every function’s output has a variable. We now have:

\[c=a+b\]

\[d=b+1\]

\[e=c*d\]

To create a computational graph, we make each of these operations, along with the input variables, into nodes. When one node’s value is the input to another node, an arrow goes from one to another.

These sorts of graphs come up all the time in computer science, especially in talking about functional programs. They are very closely related to the notions of dependency graphs and call graphs. They’re also the core abstraction behind the popular deep learning framework Theano.

We can evaluate the expression by setting the input variables to certain values and computing nodes up through the graph. For example, let’s set \(a=2\) and \(b=1\):

The expression evaluates to \(6\).

If one wants to understand derivatives in a computational graph, the key is to understand derivatives on the edges. If \(a\) directly affects \(c\), then we want to know how it affects \(c\). If \(a\) changes a little bit, how does \(c\) change? We call this the partial derivative of \(c\) with respect to \(a\).

To evaluate the partial derivatives in this graph, we need the sum rule and the product rule:

\[\frac{\partial}{\partial a}(a+b) = \frac{\partial a}{\partial a} + \frac{\partial b}{\partial a} = 1\]

\[\frac{\partial}{\partial u}uv = u\frac{\partial v}{\partial u} + v\frac{\partial u}{\partial u} = v\]

Below, the graph has the derivative on each edge labeled.

What if we want to understand how nodes that aren’t directly connected affect each other? Let’s consider how \(e\) is affected by \(a\). If we change \(a\) at a speed of 1, \(c\) also changes at a speed of \(1\). In turn, \(c\) changing at a speed of \(1\) causes \(e\) to change at a speed of \(2\). So \(e\) changes at a rate of \(1*2\) with respect to \(a\).

The general rule is to sum over all possible paths from one node to the other, multiplying the derivatives on each edge of the path together. For example, to get the derivative of \(e\) with respect to \(b\) we get:

\[\frac{\partial e}{\partial b}= 1*2 + 1*3\]

---

## [Neural Networks, Types, and Functional Programming](https://colah.github.io/posts/2015-09-NN-Types-FP/)

Posted on September 3, 2015

Deep learning, despite its remarkable successes, is a young field. While models called artificial neural networks have been studied for decades, much of that work seems only tenuously connected to modern results.

It’s often the case that young fields start in a very ad-hoc manner. Later, the mature field is understood very differently than it was understood by its early practitioners. For example, in taxonomy, people have grouped plants and animals for thousands of years, but the way we understood what we were doing changed a lot in light of evolution and molecular biology. In chemistry, we have explored chemical reactions for a long time, but what we understood ourselves to do changed a lot with the discovery of irreducible elements, and again later with models of the atom. Those are grandiose examples, but the history of science and mathematics has seen this pattern again and again, on many different scales.

It seems quite likely that deep learning is in this ad-hoc state.

At the moment, deep learning is held together by an extremely successful tool. This tool doesn’t seem fundamental; it’s something we’ve stumbled on, with seemingly arbitrary details that change regularly. As a field, we don’t yet have some unifying insight or shared understanding. In fact, the field has several competing narratives!

I think it is very likely that, reflecting back in 30 years, we will see deep learning very differently.

If we think we’ll probably see deep learning very differently in 30 years, that suggests an interesting question: how are we going to see it? Of course, no one can actually know how we’ll come to understand the field. But it is interesting to speculate.

At present, three narratives are competing to be the way we understand deep learning. There’s the neuroscience narrative, drawing analogies to biology. There’s the representations narrative, centered on transformations of data and the manifold hypothesis. Finally, there’s a probabilistic narrative, which interprets neural networks as finding latent variables. These narratives aren’t mutually exclusive, but they do present very different ways of thinking about deep learning.

This essay extends the representations narrative to a new answer: deep learning studies a connection between optimization and functional programming.

In this view, the representations narrative in deep learning corresponds to type theory in functional programming. It sees deep learning as the junction of two fields we already know to be incredibly rich. What we find, seems so beautiful to me, feels so natural, that the mathematician in me could believe it to be something fundamental about reality.

This is an extremely speculative idea. I am not arguing that it is true. I wish to argue only that it is plausible, that one could imagine deep learning evolving in this direction. To be clear: I am primarily making an aesthetic argument, rather than an argument of fact. I wish to show that this is a natural and elegant idea, encompassing what we presently call deep learning.

The distinctive property of deep learning is that it studies deep neural networks – neural networks with many layers. Over the course of multiple layers, these models progressively bend data, warping it into a form where it is easy to solve the given task.

The details of these layers change every so often.1 What has remained constant is that there is a sequence of layers.

Each layer is a function, acting on the output of a previous layer. As a whole, the network is a chain of composed functions. This chain of composed functions is optimized to perform a task.

Every model in deep learning that I am aware of involves optimizing composed functions. I believe this is the heart of what we are studying.

With every layer, neural networks transform data, molding it into a form that makes their task easier to do. We call these transformed versions of data “representations.”

Representations correspond to types.

At their crudest, types in computer science are a way of embedding some kind of data in \(n\) bits. Similarly, representations in deep learning are a way to embed a data manifold in \(n\) dimensions.

Just as two functions can only be composed together if their types agree, two layers can only be composed together when their representations agree. Data in the wrong representation is nonsensical to a neural network. Over the course of training, adjacent layers negotiate the representation they will communicate in; the performance of the network depends on data being in the representation the network expects.

In the case of very simple neural network architectures, where there’s just a linear sequence of layers, this isn’t very interesting. The representation of one layer’s output needs to match the representation of the next layer’s input – so what? It’s a trivial and boring requirement.

---

