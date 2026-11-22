using System.Reflection;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OpenAI;
using System.ClientModel;
using System.ClientModel.Primitives;

namespace Librarian.Adapters.Mistral;

internal static class MistralAgentFactory
{
    internal static AIAgent CreateExtractAgent(IServiceProvider services, string apiKey, string baseUrl, string model, string reasoningEffort, int maxRounds)
    {
        var loggerFactory = services.GetRequiredService<ILoggerFactory>();

        var pipeline = Chat(apiKey, baseUrl, model).AsBuilder()
            .UseFunctionInvocation(loggerFactory, f => f.MaximumIterationsPerRequest = maxRounds)
            .Build(services);

        var agent = new ChatClientAgent(pipeline, new ChatClientAgentOptions
        {
            Name = "extractAgent",
            ChatOptions = new ChatOptions
            {
                Instructions = InstructionsText(),
                Reasoning = new ReasoningOptions
                {
                    Effort = reasoningEffort switch
                    {
                        "low" => ReasoningEffort.Low,
                        "medium" => ReasoningEffort.Medium,
                        "high" => ReasoningEffort.High,
                        _ => throw new InvalidOperationException($"Ingest:Extract:ReasoningEffort '{reasoningEffort}' is not one of low, medium, high."),
                    },
                },
            },
        }, loggerFactory, services);

        return new OpenTelemetryAgent(agent, "Microsoft.Agents.AI");
    }

    internal static AIAgent CreateRefineAgent(IServiceProvider services, string apiKey, string baseUrl, string model)
    {
        var loggerFactory = services.GetRequiredService<ILoggerFactory>();

        var agent = new ChatClientAgent(Chat(apiKey, baseUrl, model), new ChatClientAgentOptions
        {
            Name = "refineAgent",
            ChatOptions = new ChatOptions { Temperature = 0 },
        }, loggerFactory, services);

        return new OpenTelemetryAgent(agent, "Microsoft.Agents.AI");
    }

    private static IChatClient Chat(string apiKey, string baseUrl, string model)
    {
        var openAiClient = new OpenAIClient(new ApiKeyCredential(apiKey), new OpenAIClientOptions
        {
            Endpoint = new Uri(baseUrl),
            RetryPolicy = new ClientRetryPolicy(3),
            UserAgentApplicationId = "librarian",
            Transport = new HttpClientPipelineTransport(new HttpClient(new ThinkingShim())),
        });
        return openAiClient.GetChatClient(model).AsIChatClient();
    }

    private static string InstructionsText()
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream("Librarian.Adapters.Mistral.Instructions.extract.md")
            ?? throw new InvalidOperationException("extract.md is not an embedded resource of Librarian.Adapters.");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd().Trim();
    }
}
