import tensorflow as tf
import numpy as np
import time
from optimizer import SVGD
import matplotlib.pyplot as plt

# hyperparams
num0 = 200  # number of samples in class0 (<400)
num_particles = 100  # number of ensembles (SVGD particles)
num_iterations = 1000  # number of training iterations
seed = 0

# random seeds
np.random.seed(seed)
tf.set_random_seed(seed)

# data generation
num1 = 400 - num0
mean0 = np.array([-3, -3])
std0 = np.array([0.5, 0.5])
mean1 = np.array([3, 3])
std1 = np.array([0.5, 0.5])
x0 = np.tile(mean0, (num0, 1)) + std0 * np.random.randn(num0, 2)
x1 = np.tile(mean1, (num1, 1)) + std1 * np.random.randn(num1, 2)
y0 = np.zeros((x0.shape[0], 1))
y1 = np.ones((x1.shape[0], 1))

x = np.concatenate([x0, x1], axis=0)
y = np.concatenate([y0, y1], axis=0)
D = np.hstack([x, y])
np.random.shuffle(D)
x = np.array(D[:, 0:2], dtype=np.float32)
y = np.array(D[:, 2:], dtype=np.float32)
x_train = x[:300]
y_train = y[:300]
x_test = x[300:]
y_test = y[300:]

x_ = tf.placeholder(tf.float32, [None, 2])
y_ = tf.placeholder(tf.float32, [None, 1])


def network(inputs, labels, scope):
    net = inputs
    with tf.variable_scope(scope):
        for _ in range(2):
            net = tf.layers.dense(net, 100, activation=tf.nn.tanh)
        logits = tf.layers.dense(net, 1)
        # Based on the model assumption
        #       p(w, D) := p(w) \prod_{i=1}^N p(x_i) p(0|x_i,w)^{1-y_i} p(1|x_i,w)^{y_i},
        # the log likelihood is equal to the negative cross entropy up to unknown normalization constant.
        # Note that p(1|x_i, w) is modeled by neural network in this problem.
        log_likelihood = - tf.nn.sigmoid_cross_entropy_with_logits(labels=labels, logits=logits)
        variables = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=scope)
        prob_1_x_w = tf.nn.sigmoid(logits)
        # uniform prior assumption
        gradients = tf.gradients(log_likelihood, variables)

    return gradients, variables, prob_1_x_w


grads_list, vars_list, prob_1_x_w_list = [], [], []
for i in range(num_particles):
    grads, vars, prob_1_x_w = network(x_, y_, 'p{}'.format(i))
    grads_list.append(grads)
    vars_list.append(vars)
    prob_1_x_w_list.append(prob_1_x_w)


def make_gradient_optimizer():
    return tf.train.AdamOptimizer(learning_rate=0.001)


optimizer = SVGD(grads_list=grads_list,
                 vars_list=vars_list,
                 make_gradient_optimizer=make_gradient_optimizer)

# marginalization using MC approximation
prob_1_x = tf.reduce_mean(tf.stack(prob_1_x_w_list), axis=0)

with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())

    # training
    start_time = time.time()
    for _ in range(num_iterations):
        sess.run(optimizer.update_op, feed_dict={x_: x_train, y_: y_train})
    end_time = time.time()

    print('{} sec per iteration'.format(end_time - start_time))

    # test via predictive distribution
    p1 = sess.run(prob_1_x, feed_dict={x_: x_test})
    classification = np.array(p1) > 0.5
    error_rate = np.sum(classification != y_test) / y_test.shape[0] * 100
    print('Error rate: {}%'.format(error_rate))

    # plot
    fig = plt.figure(figsize=(5, 5))
    num_rows, num_cols = 1, 1

    ax = fig.add_subplot(num_rows, num_cols, 1)
    x0, x1 = np.linspace(-7, 7, 50), np.linspace(-7, 7, 50)
    x0_grid, x1_grid = np.meshgrid(x0, x1)
    x_grid = np.hstack([x0_grid.reshape(-1, 1), x1_grid.reshape(-1, 1)])
    p1_grid = sess.run(prob_1_x, feed_dict={x_: x_grid}).reshape(x0_grid.shape)

    cont = ax.contour(x0_grid, x1_grid, p1_grid, 50, cmap=plt.cm.coolwarm, zorder=0)
    where0, where1 = np.where(y_train == 0), np.where(y_train == 1)

    x0 = x_train[np.where(y_train[:, 0] == 0)]
    x1 = x_train[np.where(y_train[:, 0] == 1)]
    ax.scatter(x0[:, 0], x0[:, 1], s=1, c='blue', zorder=1)
    ax.scatter(x1[:, 0], x1[:, 1], s=1, c='red', zorder=2)
    ax.set_title('Predictive distribution $p(1|(x_0, x_1))$')
    ax.set_xlabel('$x_0$')
    ax.set_ylabel('$x_1$')
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.set_aspect('equal', 'box')
    ax.grid(b=True)
    fig.colorbar(cont)

    plt.show()