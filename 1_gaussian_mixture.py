import tensorflow as tf
import numpy as np
import time
from optimizer import SVGD, Ensemble, AdagradOptimizer
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde


# hyperparams
num_particles = 100  # number of ensembles (SVGD particles)
num_iterations = 3000  # number of training iterations
learning_rate = 0.01
seed = 0
algorithm = 'svgd' # 'svgd' or 'ensemble'

# random seeds
np.random.seed(seed)

# initializer with q(x) distribution
initial_xs = np.array(np.random.normal(-10, 1, (100, 1)), dtype=np.float32).reshape(-1)

def network(scope):

    def log_normal(x, m, s):
        return - (x - m) ** 2 / 2. / s ** 2 - tf.log(s) - 0.5 * tf.log(2. * np.pi)

    with tf.variable_scope(scope):
        x = tf.Variable(initial_xs[eval(scope[1])])
        log_prob0, log_prob1 = log_normal(x, -2., 1.), log_normal(x, 2., 1.)
        # log of target distribution p(x)
        log_p = tf.reduce_logsumexp(tf.stack([log_prob0, log_prob1, log_prob1]), axis=0) - tf.log(3.)
        variables = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=scope)
        gradients = tf.gradients(log_p, variables)
    return gradients, variables


grads_list, vars_list = [], []
for i in range(num_particles):
    grads, vars = network('p{}'.format(i))
    grads_list.append(grads)
    vars_list.append(vars)


def make_gradient_optimizer():
    return AdagradOptimizer(learning_rate=learning_rate)
    #return tf.train.AdamOptimizer(learning_rate=learning_rate)


if algorithm == 'svgd':
    optimizer = SVGD(grads_list=grads_list,
                     vars_list=vars_list,
                     make_gradient_optimizer=make_gradient_optimizer)
elif algorithm == 'ensemble':
    optimizer = Ensemble(grads_list=grads_list,
                         vars_list=vars_list,
                         make_gradient_optimizer=make_gradient_optimizer)
else:
    raise NotImplementedError

xs = tf.trainable_variables()

with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    initial_xs = sess.run(xs)

    # training
    start_time = time.time()
    for _ in range(num_iterations):
        sess.run(optimizer.update_op)
    end_time = time.time()
    print('{} sec per iteration'.format(end_time - start_time))
    final_xs = sess.run(xs)

    # plot
    fig = plt.figure(figsize=(5, 5))
    num_rows, num_cols = 1, 1

    ax = fig.add_subplot(num_rows, num_cols, 1)
    x_grid = np.linspace(-15, 15, 200)

    initial_density = gaussian_kde(initial_xs, 0.5)
    ax.plot(x_grid, initial_density(x_grid), color='green', label='0th iteration')
    ax.scatter(initial_xs, np.zeros_like(initial_xs), color='green')

    final_density = gaussian_kde(final_xs, 0.5)
    ax.plot(x_grid, final_density(x_grid), color='red', label='{}th iteration'.format(num_iterations))
    ax.scatter(final_xs, np.zeros_like(final_xs), color='red')

    def log_normal(x, m, s):
        return - (x - m) ** 2 / 2. / s ** 2 - np.log(s) - 0.5 * np.log(2. * np.pi)
    target_density = np.exp(log_normal(x_grid, -2., 1.)) / 3 + np.exp(log_normal(x_grid, 2., 1.)) * 2 / 3
    ax.plot(x_grid, target_density, 'r--')

    ax.set_xlim([-15, 15])
    ax.set_ylim([0, 0.4])
    ax.legend()

    plt.show()
