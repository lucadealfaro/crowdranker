# -*- coding: utf-8 -*-

import numpy as np


def backtracking_line_search(x, delta_x, f, grad_f, alpha=0.3, beta=0.7):
    """ Method implements backtracking line search along
    descent direction delta_x (Boyd, algorithm 9.2, page 464)."""
    t = 1
    grad = grad_f(x)
    while True:
        val1 = f(x + t * delta_x)
        val2 = f(x) + alpha * t * np.dot(grad, delta_x)
        if val1 <= val2:
            return t
        t = beta * t


def get_argmin(x_0, f=None, grad_f=None,
               hess=None, hess_inv=None, eta=0.1,
               epsilon=0.001,
               algo_type='gradient_descent'):
    """ arguments:
        x_0 - starting point of descent.
        f - the objective function to be minimized.
        grad_f - gradient of f.
        hess - hessian matrix of f at given point.
        hess_inv - inverse of hessian matrix at given point.
        algo_type - can be "gradient_descent", "newtons_method".
        eta - used in stopped conditions in gradient descent.
        epsilon - is a toleralnce for Newton's method (Boyd, algo 9.5, p487)
    """
    if f is None or grad_f is None:
        print 'The objective function or its gradient is not specified.'
        return
    # Gradien descent
    if algo_type == 'gradient_descent':
        x = x_0
        while True:
            delta_x = -grad_f(x)
            # Checking for the stopping condition.
            if np.dot(delta_x, delta_x) ** 0.5 < eta:
                return x
            t = backtracking_line_search(x, delta_x, f, grad_f)
            x = x + t * delta_x
    # Newton's method
    elif algo_type == 'newtons_method':
        if hess is None and hess_inv is None:
            return
        # Computing the Newton step and decrement.
        x = x_0
        while True:
            grad = grad_f(x)
            # Calculating inverse of Hessian matrix (not the best practice,
            # there are ways of using Cholesky factorization,
            # but we can optimize later if we need it)
            if hess_inv is not None:
                inv = hess_inv(x)
                print 'using inverse of the hessian'
            else:
                inv = np.linalg.inv(hess(x))
            delta_x = - np.dot(inv, grad)
            lambda_square = np.dot(grad, np.dot(inv, grad))
            # Stopping criterion.
            if lambda_square <= 2 * epsilon:
                return x
            t = backtracking_line_search(x, delta_x, f, grad_f)
            x = x + t * delta_x
    else:
        print "Optimization algorithm is no specified"
        return

if __name__ == "__main__":
    # Testing on quadratic problem: sum [(d_i)^2 * (x_i - a_i)^2 + b_i x_i + c]
    import random
    num_dim = 100
    a = np.arange(num_dim)
    b = np.arange(num_dim)
    #d = (np.arange(num_dim) + 1) * 0.5
    d = np.zeros(num_dim) + 1
    random.shuffle(a)
    random.shuffle(b)
    random.shuffle(d)
    c = 10
    def f(x):
        return np.dot(d * (x - a), d * (x - a)) + np.dot(x, b) + c
    def grad_f(x):
        return 2 * d * d * (x - a) + b
    def hess(x):
        return 2 * np.diag(d ** 2)
    x_0 = np.arange(num_dim)
    # True solution.
    argmin_true = a - 0.5 * np.dot(np.linalg.inv(np.diag(d**2)), b)
    min_true = f(argmin_true)

    print 'True min is ', min_true
    # Solution using gradient descent.
    argmin_grad = get_argmin(x_0, f, grad_f)
    print 'Min value via gradient descent is', f(argmin_grad)
    # Solution using Newtons method.
    argmin_newton = get_argmin(x_0, f, grad_f, hess, algo_type="newtons_method")
    print 'Min value via Newton\'s method is', f(argmin_newton)
